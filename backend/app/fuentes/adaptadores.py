"""Adapter: cada origen convierte su formato a PublicacionImportada.

Las URLs se verificaron en respuestas HTTP reales el 25/11/2026. No se consulta
una URL elegida por el usuario ni se eluden bloqueos de acceso.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import json
import re
import time
import unicodedata
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, field_validator
from ..catalogs import AREQUIPA_DISTRICTS

LIMA = ZoneInfo("America/Lima")
URL_LISTA = "https://www.gob.pe/institucion/sedapar/noticias"
URL_CORTES = "https://cortedeagua.net.pe/api.php?empresa=SEDAPAR&dias=0"
URL_PUNTOS = (
    "https://cortedeagua.net.pe/api.php?action=cisternas&empresa=SEDAPAR&ultimos=10"
)
URL_ONG = "https://www.manosunidas.org/que-hacemos/agua"


def normalizar(texto):
    return " ".join(
        "".join(
            c
            for c in unicodedata.normalize("NFKD", str(texto or ""))
            if not unicodedata.combining(c)
        )
        .lower()
        .split()
    )


def reconocer_distritos(texto):
    """Catálogo de la provincia. No confunde Miraflores con Alto Selva Alegre."""
    limpio = normalizar(texto)
    # Evita confundir nombres de otros ámbitos con un distrito de Arequipa.
    limpio = re.sub(
        r"\bsan juan de miraflores\b|\blima cercado\b|\bcercado de lima\b", "", limpio
    )
    resultado = [
        d
        for d in AREQUIPA_DISTRICTS
        if re.search(r"(?<!\w)" + re.escape(normalizar(d)) + r"(?!\w)", limpio)
    ]
    if "cercado" in limpio and "Arequipa" not in resultado:
        resultado.append("Arequipa")
    if re.search(r"\bhunter\b", limpio) and "Jacobo Hunter" not in resultado:
        resultado.append("Jacobo Hunter")
    if (
        "jose luis bustamante" in limpio
        and "José Luis Bustamante y Rivero" not in resultado
    ):
        resultado.extend(d for d in AREQUIPA_DISTRICTS if "Bustamante" in d)
    return list(dict.fromkeys(resultado))


def fecha_lima(valor):
    if not valor:
        return None
    try:
        texto = str(valor).strip().replace("Z", "+00:00")
        if re.match(r"^\d{2}/\d{2}/\d{4}", texto):
            m = re.search(r"(\d{2}/\d{2}/\d{4})\s*[–—-]?\s*(\d{1,2}:\d{2})", texto)
            fecha = (
                datetime.strptime(m[1] + " " + m[2], "%d/%m/%Y %H:%M")
                if m
                else datetime.strptime(texto[:10], "%d/%m/%Y")
            )
        else:
            fecha = datetime.fromisoformat(texto)
        return (
            fecha.replace(tzinfo=LIMA)
            if fecha.tzinfo is None
            else fecha.astimezone(LIMA)
        ).isoformat()
    except (ValueError, TypeError):
        return None


def fecha_publicacion_es(texto):
    meses = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()
    m = re.search(
        r"(\d{1,2}) de (\w+) de (\d{4})\s*[-–]?\s*(?:(\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?)?",
        normalizar(texto),
    )
    if not m or m[2] not in meses:
        return None
    try:
        hora = int(m[4] or 0)
        if m[6]:
            hora = hora % 12 + (12 if m[6] == "p" else 0)
        return datetime(
            int(m[3]),
            meses.index(m[2]) + 1,
            int(m[1]),
            hora,
            int(m[5] or 0),
            tzinfo=LIMA,
        ).isoformat()
    except ValueError:
        return None


class PublicacionImportada(BaseModel):
    categoria: str
    identificador: str = Field(min_length=1, max_length=240)
    datos: dict
    revision: str = "automatico"
    observacion: str = ""

    @field_validator("categoria")
    @classmethod
    def validar_categoria(cls, valor):
        if valor not in ("corte", "punto", "orientacion"):
            raise ValueError("Categoría desconocida")
        return valor

    @field_validator("datos")
    @classmethod
    def validar_datos(cls, datos):
        for campo in ("url", "url_original"):
            if datos.get(campo) and urlparse(datos[campo]).scheme != "https":
                raise ValueError("La fuente debe tener enlace HTTPS")
        if any(d not in AREQUIPA_DISTRICTS for d in datos.get("distritos", [])):
            raise ValueError("Distrito fuera del catálogo")
        if not datos.get("titulo") or not datos.get("url"):
            raise ValueError("Falta título o fuente")
        return datos


@dataclass
class ResultadoConsulta:
    publicaciones: list[PublicacionImportada] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)


class ClientePublico:
    """Descargas limitadas, dos intentos y caché condicional. Un error nunca vacía la BD."""

    def __init__(self, carpeta=".cache_fuentes"):
        self.carpeta = Path(carpeta)
        self.carpeta.mkdir(exist_ok=True)
        self.cliente = httpx.Client(
            timeout=httpx.Timeout(20, connect=10),
            follow_redirects=True,
            headers={"User-Agent": "AguaReservaAQP/1.0 (consulta publica educativa)"},
        )

    def cerrar(self):
        self.cliente.close()

    def descargar(self, url):
        if urlparse(url).hostname not in (
            "www.gob.pe",
            "cortedeagua.net.pe",
            "www.manosunidas.org",
        ):
            raise ValueError("Origen no permitido")
        archivo = self.carpeta / (sha256(url.encode()).hexdigest() + ".json")
        try:
            cache = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cache = {}
        # Siempre revalida: obtener un documento de caché no simula una consulta exitosa.
        cabeceras = {}
        if cache.get("etag"):
            cabeceras["If-None-Match"] = cache["etag"]
        if cache.get("modificado"):
            cabeceras["If-Modified-Since"] = cache["modificado"]
        for intento in range(2):
            try:
                with self.cliente.stream("GET", url, headers=cabeceras) as r:
                    if r.status_code == 304 and "cuerpo" in cache:
                        return cache["cuerpo"]
                    r.raise_for_status()
                    partes = []
                    total = 0
                    for parte in r.iter_bytes():
                        total += len(parte)
                        if total > 2_000_000:
                            raise ValueError("Respuesta demasiado grande")
                        partes.append(parte)
                    cuerpo = b"".join(partes).decode("utf-8", errors="replace")
                    archivo.write_text(
                        json.dumps(
                            {
                                "cuerpo": cuerpo,
                                "etag": r.headers.get("etag"),
                                "modificado": r.headers.get("last-modified"),
                            },
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
                    return cuerpo
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500 or intento:
                    raise
            except httpx.TransportError:
                if intento:
                    raise
            time.sleep(0.5)
        raise RuntimeError("No se pudo consultar la fuente")


class AdaptadorFuente(ABC):
    clave: str
    nombre: str
    tipo: str
    url: str
    intervalo: int

    @abstractmethod
    def consultar(self, cliente): ...


def extraer_aviso_oficial(html, url):
    sopa = BeautifulSoup(html, "html.parser")
    principal = sopa.find("main") or sopa
    titulo = sopa.find("h1")
    texto = principal.get_text(" ", strip=True)
    # Segmenta por rótulos explícitos; no usa fecha de publicación como inicio del corte.
    patron = r"(Motivo|Fecha y hora de cierre|Fecha y hora aproximada de reposici[oó]n|Distrito\(s\)|Circuito\(s\)|Zonas afectadas)\s*:"
    partes = re.split(patron, texto, flags=re.I)
    campos = {
        normalizar(partes[i]): partes[i + 1].split("Esta noticia pertenece")[0].strip()
        for i in range(1, len(partes) - 1, 2)
    }
    distritos = reconocer_distritos(campos.get("distrito(s)", ""))
    if not distritos:
        return None
    inicio = fecha_lima(campos.get("fecha y hora de cierre"))
    fin = fecha_lima(campos.get("fecha y hora aproximada de reposicion"))
    revision = "automatico"
    observacion = ""
    if (
        not inicio
        or not fin
        or datetime.fromisoformat(fin) <= datetime.fromisoformat(inicio)
    ):
        revision = "pendiente"
        observacion = (
            "Horario incompleto o inconsistente; revisar la publicación original."
        )
    codigo = re.search(r"\d{1,4}-\d{4}", titulo.get_text() if titulo else "")
    return PublicacionImportada(
        categoria="corte",
        identificador=url,
        revision=revision,
        observacion=observacion,
        datos={
            "titulo": titulo.get_text(" ", strip=True) if titulo else "Aviso Sedapar",
            "codigo": codigo[0] if codigo else None,
            "motivo": campos.get("motivo", ""),
            "distritos": distritos,
            "zonas": campos.get("zonas afectadas", ""),
            "circuitos": campos.get("circuito(s)", ""),
            "inicio": inicio,
            "fin_estimado": fin,
            "publicado": fecha_publicacion_es(texto),
            "tipo": "imprevisto"
            if "imprevista" in normalizar(texto)
            else "programado"
            if "programada" in normalizar(texto)
            else "sin_clasificar",
            "url": url,
            "url_original": url,
            "origen_verificado": True,
        },
    )


class AdaptadorSedapar(AdaptadorFuente):
    clave = "sedapar_gob"
    nombre = "Sedapar · Gob.pe"
    tipo = "oficial"
    url = URL_LISTA
    intervalo = 60

    def consultar(self, cliente):
        html = cliente.descargar(self.url)
        sopa = BeautifulSoup(html, "html.parser")
        enlaces = list(
            dict.fromkeys(
                urljoin(self.url, a["href"])
                for a in sopa.select("a[href]")
                if "/institucion/sedapar/noticias/" in a["href"]
            )
        )[:25]
        if not enlaces:
            raise ValueError(
                "Cambió el listado de Sedapar: no se reconocen enlaces de noticias."
            )
        resultado = ResultadoConsulta()
        for enlace in enlaces:
            try:
                aviso = extraer_aviso_oficial(cliente.descargar(enlace), enlace)
                if aviso:
                    resultado.publicaciones.append(aviso)
            except (httpx.HTTPError, ValueError) as e:
                resultado.advertencias.append(f"{enlace}: {str(e)[:180]}")
        if len(resultado.advertencias) == len(enlaces):
            raise ValueError("Ningún detalle de Sedapar pudo consultarse.")
        return resultado


class AdaptadorCortesComplementarios(AdaptadorFuente):
    clave = "cortes_complementarios"
    nombre = "Cortedeagua.net.pe · cortes"
    tipo = "complementaria"
    url = "https://cortedeagua.net.pe/arequipa/"
    intervalo = 30

    def consultar(self, cliente):
        respuesta = json.loads(cliente.descargar(URL_CORTES))
        if respuesta.get("ok") is not True or not isinstance(
            respuesta.get("data"), list
        ):
            raise ValueError("Formato de cortes no reconocido")
        resultado = ResultadoConsulta()
        for fila in respuesta["data"]:
            if fila.get("empresa") != "SEDAPAR" or str(fila.get("agua", 1)) == "0":
                continue
            distritos = reconocer_distritos(fila.get("municipalidad"))
            if not distritos:
                continue
            inicio = fecha_lima(fila.get("fec_deteccion"))
            fin = fecha_lima(fila.get("fec_estimada"))
            observacion = "Fuente complementaria; no se verificó el comunicado original. No confirma una afectación domiciliaria."
            if (
                not inicio
                or not fin
                or not 0
                < (
                    datetime.fromisoformat(fin) - datetime.fromisoformat(inicio)
                ).total_seconds()
                <= 31 * 86400
            ):
                fin = None
                observacion += " Horario incompleto o inconsistente."
            identificador = str(fila.get("cod_incidencia") or fila.get("id") or "")
            if not identificador:
                continue
            resultado.publicaciones.append(
                PublicacionImportada(
                    categoria="corte",
                    identificador=identificador,
                    datos={
                        "titulo": str(fila.get("causa") or "Aviso de corte")[:240],
                        "codigo": identificador,
                        "motivo": str(fila.get("causa") or "")[:1000],
                        "distritos": distritos,
                        "zonas": str(fila.get("areas_afectadas") or "")[:10000],
                        "circuitos": str(fila.get("infor_web") or "")[:1000],
                        "inicio": inicio,
                        "fin_estimado": fin,
                        # creado_en es alta en el recopilador, NO publicación oficial.
                        "publicado": None,
                        "registrado_origen": fecha_lima(fila.get("creado_en")),
                        "tipo": str(fila.get("tipo_incid") or "").lower(),
                        "url": self.url,
                        "url_original": None,
                        "origen_verificado": False,
                    },
                    revision="pendiente",
                    observacion=observacion,
                )
            )
        return resultado


class AdaptadorCisternas(AdaptadorFuente):
    clave = "cisternas_complementarias"
    nombre = "Cortedeagua.net.pe · cisternas"
    tipo = "complementaria"
    url = "https://cortedeagua.net.pe/arequipa/"
    intervalo = 30

    def consultar(self, cliente):
        respuesta = json.loads(cliente.descargar(URL_PUNTOS))
        if respuesta.get("ok") is not True or not isinstance(
            respuesta.get("data"), list
        ):
            raise ValueError("Formato de cisternas no reconocido")
        resultado = ResultadoConsulta()
        for f in respuesta["data"]:
            distritos = reconocer_distritos(f.get("distrito"))
            if not distritos or not f.get("zona_reparto"):
                continue
            fecha = str(f.get("fecha") or "")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
                continue
            try:
                datetime.strptime(fecha, "%Y-%m-%d")
            except ValueError:
                continue
            datos = {
                "titulo": str(f["zona_reparto"])[:240],
                "direccion": str(f["zona_reparto"])[:1000],
                "distritos": distritos,
                "tipo_punto": "reparto_cisterna",
                "fecha_atencion": fecha,
                "horario": str(f.get("hora_inicio") or "Sin hora anunciada"),
                "codigo": str(f.get("aviso") or ""),
                "latitud": None,
                "longitud": None,
                "procedencia_coordenadas": None,
                "coordenadas_verificadas": False,
                "publicado": None,
                "url": self.url,
                "url_original": None,
                "origen_verificado": False,
            }
            clave = "|".join(
                [
                    fecha,
                    str(f.get("aviso") or ""),
                    ",".join(distritos),
                    normalizar(f["zona_reparto"]),
                ]
            )
            resultado.publicaciones.append(
                PublicacionImportada(
                    categoria="punto",
                    identificador=sha256(clave.encode()).hexdigest(),
                    datos=datos,
                    revision="pendiente",
                    observacion="Reparto anunciado por un recopilador. Confirmar horario y atención en el comunicado original; no es una garantía de atención.",
                )
            )
        return resultado


class AdaptadorManosUnidas(AdaptadorFuente):
    clave = "manos_unidas"
    nombre = "Manos Unidas"
    tipo = "ong"
    url = URL_ONG
    intervalo = 1440

    def consultar(self, cliente):
        sopa = BeautifulSoup(cliente.descargar(self.url), "html.parser")
        titulo = sopa.find("title")
        descripcion = sopa.select_one("meta[name=description]")
        if not titulo or "Manos Unidas" not in titulo.get_text():
            raise ValueError("No se reconoce la publicación de la ONG")
        return ResultadoConsulta(
            [
                PublicacionImportada(
                    categoria="orientacion",
                    identificador=self.url,
                    datos={
                        "titulo": titulo.get_text(" ", strip=True)[:240],
                        "resumen": (
                            descripcion.get("content", "") if descripcion else ""
                        )[:500],
                        "url": self.url,
                        "url_original": self.url,
                        "publicado": None,
                        "distritos": [],
                        "alcance": "Orientación general sobre agua y saneamiento. No anuncia cortes ni puntos de reparto de Arequipa.",
                    },
                )
            ]
        )


def obtener_adaptadores():
    return [
        AdaptadorSedapar(),
        AdaptadorCortesComplementarios(),
        AdaptadorCisternas(),
        AdaptadorManosUnidas(),
    ]
