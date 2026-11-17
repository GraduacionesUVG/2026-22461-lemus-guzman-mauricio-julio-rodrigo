import time

from aplicacion import crear_aplicacion
from aplicacion.extensiones import db
from aplicacion.modelos import Pipeline, Programacion
from aplicacion.servicios.pipelines import calcular_siguiente_programacion, encolar_ejecucion
from aplicacion.utilidades.tiempo import ahora_utc


def calcular_siguiente(programacion: Programacion):
    return calcular_siguiente_programacion(programacion.tipo_frecuencia, programacion.configuracion_frecuencia, zona_horaria=programacion.zona_horaria)


def ejecutar_programador() -> None:
    app = crear_aplicacion()
    with app.app_context():
        while True:
            ahora = ahora_utc()
            programaciones = Programacion.query.filter(Programacion.activo == True, Programacion.siguiente_ejecucion <= ahora).all()
            for programacion in programaciones:
                pipeline = Pipeline.query.get(programacion.pipeline_id)
                if pipeline and pipeline.activo:
                    entorno_id = programacion.configuracion_frecuencia.get("entorno_id")
                    if entorno_id:
                        encolar_ejecucion(programacion.pipeline_id, entorno_id, "programada")
                programacion.siguiente_ejecucion = calcular_siguiente(programacion)
            db.session.commit()
            time.sleep(30)


if __name__ == "__main__":
    ejecutar_programador()
