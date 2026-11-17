from uuid import UUID

from flask import Blueprint, Response, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from aplicacion.extensiones import db
from aplicacion.metricas.servicio import calcular_resumen_metricas, comparar_evaluacion, crear_reporte_evaluacion_csv
from aplicacion.modelos import MedicionEvaluacion, Proyecto

from aplicacion.servicios.yaml_configuracion import exportar_proyecto_yaml, importar_configuracion_yaml, previsualizar_importacion_yaml, validar_configuracion_yaml
from aplicacion.utilidades.respuestas import respuesta_exitosa


bp = Blueprint("metricas_yaml", __name__, url_prefix="/api")


@bp.get("/metricas/resumen")
@jwt_required()
def resumen_metricas():
    return respuesta_exitosa(calcular_resumen_metricas())


@bp.get("/metricas/tendencias")
@jwt_required()
def tendencias_metricas():
    return respuesta_exitosa({"elementos": []})


@bp.get("/metricas/reporte-evaluacion.csv")
@jwt_required()
def reporte_evaluacion_csv():
    return Response(
        crear_reporte_evaluacion_csv(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=reporte_evaluacion.csv"},
    )


@bp.get("/evaluaciones")
@jwt_required()
def listar_evaluaciones():
    elementos = MedicionEvaluacion.query.order_by(MedicionEvaluacion.creado_en.desc()).all()
    return respuesta_exitosa({"elementos": [{"id": str(item.id), "escenario": item.escenario, "enfoque": item.enfoque} for item in elementos]})


@bp.post("/evaluaciones")
@jwt_required()
def crear_evaluacion():
    datos = request.get_json() or {}
    medicion = MedicionEvaluacion(**datos)
    db.session.add(medicion)
    db.session.commit()
    return respuesta_exitosa({"id": str(medicion.id)}, 201)


@bp.get("/evaluaciones/<uuid:evaluacion_id>/comparacion")
@jwt_required()
def comparacion_evaluacion(evaluacion_id: UUID):
    return respuesta_exitosa(comparar_evaluacion(evaluacion_id))


@bp.post("/configuraciones-yaml/validar")
@jwt_required()
def validar_yaml_api():
    datos = request.get_json() or {}
    return respuesta_exitosa(validar_configuracion_yaml(datos.get("contenido", "")))


@bp.post("/configuraciones-yaml/previsualizar")
@jwt_required()
def previsualizar_yaml_api():
    datos = request.get_json() or {}
    return respuesta_exitosa(previsualizar_importacion_yaml(datos.get("contenido", "")))


@bp.post("/configuraciones-yaml/importar")
@jwt_required()
def importar_yaml_api():
    datos = request.get_json() or {}
    return respuesta_exitosa(importar_configuracion_yaml(datos.get("contenido", ""), get_jwt_identity()), 201)


@bp.get("/proyectos/<uuid:proyecto_id>/exportar-yaml")
@jwt_required()
def exportar_yaml_api(proyecto_id: UUID):
    contenido = exportar_proyecto_yaml(Proyecto.query.get_or_404(proyecto_id))
    return Response(contenido, mimetype="application/x-yaml")
