import logging
import os
from pathlib import Path
import time

from aplicacion import crear_aplicacion
from aplicacion.trabajadores.servicio import procesar_siguiente_ejecucion


def configurar_logging() -> None:
    raiz = Path(__file__).resolve().parent.parent
    directorio_logs = raiz / ".logs"
    directorio_logs.mkdir(parents=True, exist_ok=True)
    formato = "%(asctime)s %(levelname)s %(name)s %(message)s"
    logging.basicConfig(
        level=os.getenv("TRABAJADOR_LOG_LEVEL", "INFO"),
        format=formato,
        handlers=[
            logging.FileHandler(directorio_logs / "trabajador.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )


def ejecutar_trabajador() -> None:
    configurar_logging()
    app = crear_aplicacion()
    trabajador_id = os.getenv("TRABAJADOR_ID", "trabajador-local")
    logger = logging.getLogger("trabajador_qa")
    logger.info("trabajador_iniciado trabajador_id=%s", trabajador_id)
    with app.app_context():
        while True:
            try:
                ejecucion = procesar_siguiente_ejecucion(trabajador_id)
                if ejecucion is None:
                    time.sleep(5)
            except Exception:
                logger.exception("error_no_controlado_en_bucle_trabajador")
                time.sleep(5)


if __name__ == "__main__":
    ejecutar_trabajador()
