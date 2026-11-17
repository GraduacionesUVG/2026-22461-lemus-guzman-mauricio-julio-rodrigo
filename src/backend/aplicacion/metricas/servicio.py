import csv
from io import StringIO

from sqlalchemy import func, select, union_all

from aplicacion.extensiones import db
from aplicacion.modelos import Alerta, CasoPrueba, Ejecucion, Evidencia, MedicionEvaluacion, ModuloObjetivo, Notificacion, Pipeline, Proyecto, ResultadoPaso, RevisionEjecucion, RevisionPaso


def porcentaje(numerador: int, denominador: int) -> float:
    if denominador == 0:
        return 0.0
    return round(numerador / denominador * 100, 2)


def calcular_resumen_metricas() -> dict:
    ejecuciones = Ejecucion.query.count()
    tecnicamente_correctas = Ejecucion.query.filter(Ejecucion.estado.in_(["exitosa", "fallida"])).count()
    resultados = ResultadoPaso.query.count()
    fallos = ResultadoPaso.query.filter(ResultadoPaso.estado.in_(["fallida", "error_tecnico"])).count()
    evidencias = Evidencia.query.count()
    # Cada revision conserva una clasificacion actual; pendientes y no_aplica
    # no son evaluaciones concluyentes para esta tasa.
    revisiones = union_all(
        select(Alerta.clasificacion_manual.label("clasificacion")).where(
            Alerta.estado_revision == "revisada",
            Alerta.clasificacion_manual.in_(["confirmada", "falso_positivo"]),
        ),
        select(RevisionEjecucion.clasificacion).where(
            RevisionEjecucion.clasificacion.in_(["confirmada", "falso_positivo", "falso_negativo"])
        ),
        select(RevisionPaso.clasificacion).where(
            RevisionPaso.clasificacion.in_(["confirmado", "falso_positivo", "falso_negativo"])
        ),
    ).subquery()
    total_revisiones = db.session.scalar(select(func.count()).select_from(revisiones))
    falsos_positivos = db.session.scalar(
        select(func.count()).select_from(revisiones).where(revisiones.c.clasificacion == "falso_positivo")
    )
    notificaciones = Notificacion.query.count()
    notificaciones_enviadas = Notificacion.query.filter_by(estado="enviada").count()
    modulos_criticos = ModuloObjetivo.query.filter_by(critico=True, activo=True).count()
    subconsulta = db.session.query(CasoPrueba.modulo_objetivo_id).filter(CasoPrueba.activo == True).distinct()
    modulos_cubiertos = ModuloObjetivo.query.filter(ModuloObjetivo.critico == True, ModuloObjetivo.id.in_(subconsulta)).count()
    tiempo_deteccion = db.session.query(func.avg(Ejecucion.duracion_milisegundos)).filter(Ejecucion.fecha_deteccion_primer_fallo.isnot(None)).scalar() or 0
    return {
        "ejecuciones": ejecuciones,
        "porcentaje_ejecuciones_tecnicamente_correctas": porcentaje(tecnicamente_correctas, ejecuciones),
        "porcentaje_resultados_almacenados": porcentaje(resultados, resultados),
        "porcentaje_fallos_con_evidencia": porcentaje(evidencias, fallos),
        "tasa_falsos_positivos": porcentaje(falsos_positivos, total_revisiones),
        "disponibilidad_notificaciones": porcentaje(notificaciones_enviadas, notificaciones),
        "cobertura_modulos_criticos": porcentaje(modulos_cubiertos, modulos_criticos),
        "tiempo_promedio_deteccion_milisegundos": round(float(tiempo_deteccion), 2),
    }


def comparar_evaluacion(evaluacion_id) -> dict:
    medicion = MedicionEvaluacion.query.get_or_404(evaluacion_id)
    pares = MedicionEvaluacion.query.filter_by(proyecto_id=medicion.proyecto_id, escenario=medicion.escenario).all()
    return {
        "escenario": medicion.escenario,
        "mediciones": [
            {
                "enfoque": item.enfoque,
                "fallos_detectados": item.fallos_detectados,
                "tiempo_deteccion_milisegundos": item.tiempo_deteccion_milisegundos,
                "tiempo_notificacion_milisegundos": item.tiempo_notificacion_milisegundos,
                "resultados_almacenados": item.resultados_almacenados,
                "evidencias_generadas": item.evidencias_generadas,
            }
            for item in pares
        ],
    }


def crear_reporte_evaluacion_csv() -> str:
    salida = StringIO()
    escritor = csv.writer(salida)
    escritor.writerow([
        "proyecto",
        "pipelines",
        "ejecuciones",
        "exitosas",
        "fallidas",
        "errores_tecnicos",
        "alertas",
        "alertas_revisadas",
        "evidencias",
        "notificaciones",
        "notificaciones_enviadas",
        "duracion_promedio_ms",
        "cobertura_modulos_criticos",
    ])
    proyectos = Proyecto.query.order_by(Proyecto.nombre.asc()).all()
    for proyecto in proyectos:
        pipeline_ids = [pipeline.id for pipeline in Pipeline.query.filter_by(proyecto_id=proyecto.id).all()]
        ejecuciones = Ejecucion.query.filter(Ejecucion.pipeline_id.in_(pipeline_ids)).all() if pipeline_ids else []
        ejecucion_ids = [ejecucion.id for ejecucion in ejecuciones]
        alertas = Alerta.query.filter(Alerta.ejecucion_id.in_(ejecucion_ids)).all() if ejecucion_ids else []
        evidencias = Evidencia.query.filter(Evidencia.ejecucion_id.in_(ejecucion_ids)).count() if ejecucion_ids else 0
        notificaciones = Notificacion.query.filter(Notificacion.ejecucion_id.in_(ejecucion_ids)).all() if ejecucion_ids else []
        duraciones = [ejecucion.duracion_milisegundos for ejecucion in ejecuciones if ejecucion.duracion_milisegundos is not None]
        modulos_criticos = ModuloObjetivo.query.filter_by(proyecto_id=proyecto.id, critico=True, activo=True).count()
        subconsulta = db.session.query(CasoPrueba.modulo_objetivo_id).filter(CasoPrueba.proyecto_id == proyecto.id, CasoPrueba.activo == True).distinct()
        modulos_cubiertos = ModuloObjetivo.query.filter(ModuloObjetivo.proyecto_id == proyecto.id, ModuloObjetivo.critico == True, ModuloObjetivo.id.in_(subconsulta)).count()
        escritor.writerow([
            proyecto.nombre,
            len(pipeline_ids),
            len(ejecuciones),
            sum(1 for ejecucion in ejecuciones if ejecucion.estado == "exitosa"),
            sum(1 for ejecucion in ejecuciones if ejecucion.estado == "fallida"),
            sum(1 for ejecucion in ejecuciones if ejecucion.estado == "error_tecnico"),
            len(alertas),
            sum(1 for alerta in alertas if alerta.estado_revision == "revisada"),
            evidencias,
            len(notificaciones),
            sum(1 for notificacion in notificaciones if notificacion.estado == "enviada"),
            round(sum(duraciones) / len(duraciones), 2) if duraciones else 0,
            porcentaje(modulos_cubiertos, modulos_criticos),
        ])
    return salida.getvalue()
