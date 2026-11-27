"""Asistente local. La base aguareserva se crea previamente desde pgAdmin."""

from getpass import getpass
from pathlib import Path
from urllib.parse import quote


def configurar():
    ruta = Path(__file__).resolve().parent / ".env"
    if ruta.exists():
        print("Ya existe backend/.env. Se conserva para no cambiar tu conexión.")
        print("Si necesitas modificarla, edita ese archivo con VS Code.")
        return
    print("Configuración de PostgreSQL para AguaReserva AQP.")
    print("La base de datos debe llamarse aguareserva y estar creada en pgAdmin.")
    usuario = input("Usuario de PostgreSQL [postgres]: ").strip() or "postgres"
    puerto = input("Puerto [5432]: ").strip() or "5432"
    if not puerto.isdigit() or not 1 <= int(puerto) <= 65535:
        raise SystemExit("Puerto inválido.")
    clave = getpass("Contraseña de PostgreSQL (no se muestra al escribir): ")
    if not clave:
        raise SystemExit(
            "Escribe la contraseña que usas para conectar al servidor de pgAdmin."
        )
    url = f"postgresql+psycopg://{quote(usuario, safe='')}:{quote(clave, safe='')}@localhost:{puerto}/aguareserva"
    # Se codifican @, #, %, espacios y otros símbolos sin mostrar la contraseña.
    ruta.write_text(
        "DATABASE_URL="
        + url
        + "\nCOOKIE_SECURE=false\nSEDAPAR_GOB_MINUTOS=60\nCORTES_COMPLEMENTARIOS_MINUTOS=30\nCISTERNAS_COMPLEMENTARIAS_MINUTOS=30\nMANOS_UNIDAS_MINUTOS=1440\n",
        encoding="utf-8",
    )
    print("Conexión guardada. Ahora ejecuta python -m alembic upgrade head.")


if __name__ == "__main__":
    configurar()
