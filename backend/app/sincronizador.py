"""Proceso independiente: python -m app.sincronizador [--una-vez]."""

import argparse
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from .services.fuentes import sincronizar_fuentes


def ejecutar():
    try:
        resultado = sincronizar_fuentes()
        if resultado:
            logging.info("Consulta de fuentes: %s", resultado)
    except Exception:
        logging.exception(
            "No se pudo sincronizar. Revisa conexión y migraciones de la base."
        )


def iniciar():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--una-vez", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    if args.una_vez:
        print(sincronizar_fuentes(forzar=True))
        return
    ejecutar()
    reloj = BlockingScheduler(timezone="America/Lima")
    reloj.add_job(
        ejecutar,
        "interval",
        minutes=1,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    print("Sincronizador activo. Mantén esta ventana abierta. Ctrl+C para terminar.")
    try:
        reloj.start()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    iniciar()
