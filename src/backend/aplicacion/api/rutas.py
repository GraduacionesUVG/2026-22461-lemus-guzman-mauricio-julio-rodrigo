from pathlib import Path
from uuid import UUID

from flask import Blueprint, current_app, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from aplicacion.extensiones import db
from aplicacion.informes.servicio import obtener_o_generar_informe
from aplicacion.modelos import Alerta, CanalNotificacion, CasoPrueba, Entorno, Evidencia, Ejecucion, ModuloObjetivo, Monitor, Pipeline, Programacion, Proyecto, ResultadoPaso, RevisionEjecucion, RevisionPaso, Secreto
from aplicacion.monitoreo.servicio import ejecutar_monitor_api as ejecutar_monitor_api_servicio
from aplicacion.monitoreo.servicio import ejecutar_monitor_base_datos, ejecutar_monitor_http, ejecutar_monitor_tcp, resolver_cadena_conexion_base_datos
from aplicacion.notificaciones.servicio import actualizar_canal_notificacion, crear_canal_notificacion, probar_canal_notificacion
from aplicacion.seguridad.permisos import requiere_roles
from aplicacion.servicios.pipelines import actualizar_pipeline, actualizar_programacion, calcular_siguiente_programacion, crear_pipeline, crear_programacion, encolar_ejecucion
from aplicacion.servicios.proyectos import actualizar_proyecto, crear_entorno, crear_modulo, crear_proyecto, crear_secreto
from aplicacion.servicios.pruebas import actualizar_caso_prueba, crear_caso_prueba, crear_monitor
from aplicacion.servicios.serializacion import serializar_alerta, serializar_canal_notificacion, serializar_caso, serializar_entorno, serializar_ejecucion, serializar_evidencia, serializar_modulo, serializar_monitor, serializar_pipeline, serializar_programacion, serializar_proyecto, serializar_revision_ejecucion, serializar_revision_paso, serializar_secreto
from aplicacion.trabajadores.servicio import procesar_ejecucion
from aplicacion.utilidades.respuestas import respuesta_error, respuesta_exitosa
from aplicacion.utilidades.tiempo import ahora_utc, iso_utc


bp = Blueprint("api", __name__, url_prefix="/api")


def obtener_json() -> dict:
    return request.get_json() or {}


@bp.get("/proyectos")
@jwt_required()
def listar_proyectos():
    proyectos = Proyecto.query.order_by(Proyecto.creado_en.desc()).all()
    return respuesta_exitosa({"elementos": [serializar_proyecto(proyecto) for proyecto in proyectos]})


@bp.post("/proyectos")
@requiere_roles("qa", "devops")
def crear_proyecto_api():
    proyecto = crear_proyecto(obtener_json(), get_jwt_identity())
    return respuesta_exitosa(serializar_proyecto(proyecto), 201)


@bp.get("/proyectos/<uuid:proyecto_id>")
@jwt_required()
def obtener_proyecto(proyecto_id: UUID):
    return respuesta_exitosa(serializar_proyecto(Proyecto.query.get_or_404(proyecto_id)))


@bp.patch("/proyectos/<uuid:proyecto_id>")
@requiere_roles("qa", "devops")
def actualizar_proyecto_api(proyecto_id: UUID):
    return respuesta_exitosa(serializar_proyecto(actualizar_proyecto(proyecto_id, obtener_json())))


@bp.get("/proyectos/<uuid:proyecto_id>/entornos")
@jwt_required()
def listar_entornos(proyecto_id: UUID):
    entornos = Entorno.query.filter_by(proyecto_id=proyecto_id).all()
    return respuesta_exitosa({"elementos": [serializar_entorno(entorno) for entorno in entornos]})


@bp.post("/proyectos/<uuid:proyecto_id>/entornos")
@requiere_roles("qa", "devops")
def crear_entorno_api(proyecto_id: UUID):
    return respuesta_exitosa(serializar_entorno(crear_entorno(proyecto_id, obtener_json())), 201)


@bp.post("/proyectos/<uuid:proyecto_id>/modulos")
@requiere_roles("qa")
def crear_modulo_api(proyecto_id: UUID):
    return respuesta_exitosa(serializar_modulo(crear_modulo(proyecto_id, obtener_json())), 201)


@bp.get("/proyectos/<uuid:proyecto_id>/modulos")
@jwt_required()
def listar_modulos(proyecto_id: UUID):
    modulos = ModuloObjetivo.query.filter_by(proyecto_id=proyecto_id).all()
    return respuesta_exitosa({"elementos": [serializar_modulo(modulo) for modulo in modulos]})


@bp.post("/proyectos/<uuid:proyecto_id>/secretos")
@requiere_roles("administrador", "devops")
def crear_secreto_api(proyecto_id: UUID):
    return respuesta_exitosa(serializar_secreto(crear_secreto(proyecto_id, obtener_json(), get_jwt_identity())), 201)


@bp.get("/proyectos/<uuid:proyecto_id>/secretos")
@requiere_roles("administrador", "devops")
def listar_secretos(proyecto_id: UUID):
    secretos = Secreto.query.filter_by(proyecto_id=proyecto_id).all()
    return respuesta_exitosa({"elementos": [serializar_secreto(secreto) for secreto in secretos]})


@bp.get("/proyectos/<uuid:proyecto_id>/canales-notificacion")
@requiere_roles("administrador", "devops")
def listar_canales_notificacion(proyecto_id: UUID):
    canales = CanalNotificacion.query.filter_by(proyecto_id=proyecto_id).all()
    return respuesta_exitosa({"elementos": [serializar_canal_notificacion(canal) for canal in canales]})


@bp.post("/proyectos/<uuid:proyecto_id>/canales-notificacion")
@requiere_roles("administrador", "devops")
def crear_canal_notificacion_api(proyecto_id: UUID):
    canal = crear_canal_notificacion(proyecto_id, obtener_json())
    return respuesta_exitosa(serializar_canal_notificacion(canal), 201)


@bp.patch("/canales-notificacion/<uuid:canal_id>")
@requiere_roles("administrador", "devops")
def actualizar_canal_notificacion_api(canal_id: UUID):
    canal = actualizar_canal_notificacion(canal_id, obtener_json())
    return respuesta_exitosa(serializar_canal_notificacion(canal))


@bp.post("/canales-notificacion/<uuid:canal_id>/probar")
@requiere_roles("administrador", "devops")
def probar_canal_notificacion_api(canal_id: UUID):
    canal = CanalNotificacion.query.get_or_404(canal_id)
    return respuesta_exitosa(probar_canal_notificacion(canal))


@bp.get("/casos-prueba")
@jwt_required()
def listar_casos():
    casos = CasoPrueba.query.order_by(CasoPrueba.creado_en.desc()).all()
    return respuesta_exitosa({"elementos": [serializar_caso(caso) for caso in casos]})


@bp.post("/casos-prueba")
@requiere_roles("qa")
def crear_caso_api():
    return respuesta_exitosa(serializar_caso(crear_caso_prueba(obtener_json())), 201)


@bp.get("/casos-prueba/<uuid:caso_id>")
@jwt_required()
def obtener_caso(caso_id: UUID):
    return respuesta_exitosa(serializar_caso(CasoPrueba.query.get_or_404(caso_id)))


@bp.patch("/casos-prueba/<uuid:caso_id>")
@requiere_roles("qa")
def actualizar_caso_api(caso_id: UUID):
    return respuesta_exitosa(serializar_caso(actualizar_caso_prueba(caso_id, obtener_json())))


@bp.post("/casos-prueba/<uuid:caso_id>/validar")
@requiere_roles("qa")
def validar_caso_api(caso_id: UUID):
    caso = CasoPrueba.query.get_or_404(caso_id)
    return respuesta_exitosa({"valido": True, "pasos": len(caso.pasos)})


@bp.get("/monitores")
@jwt_required()
def listar_monitores():
    monitores = Monitor.query.all()
    return respuesta_exitosa({"elementos": [serializar_monitor(monitor) for monitor in monitores]})


@bp.post("/monitores")
@requiere_roles("devops", "qa")
def crear_monitor_api():
    return respuesta_exitosa(serializar_monitor(crear_monitor(obtener_json())), 201)


@bp.post("/monitores/<uuid:monitor_id>/ejecutar")
@requiere_roles("devops", "qa")
def ejecutar_monitor_api(monitor_id: UUID):
    monitor = Monitor.query.get_or_404(monitor_id)
    entorno = Entorno.query.get_or_404(monitor.entorno_id or obtener_json().get("entorno_id"))
    if monitor.tipo == "http":
        resultado = ejecutar_monitor_http(entorno.url_base, monitor.configuracion, entorno.verificar_certificado_tls, entorno.tiempo_espera_segundos)
    elif monitor.tipo == "api":
        resultado = ejecutar_monitor_api_servicio(monitor.configuracion)
    elif monitor.tipo == "tcp":
        resultado = ejecutar_monitor_tcp(monitor.configuracion)
    elif monitor.tipo == "base_datos":
        resultado = ejecutar_monitor_base_datos(monitor.configuracion, resolver_cadena_conexion_base_datos(monitor.configuracion))
    else:
        return respuesta_error("monitor_no_soportado", "El tipo de monitor indicado todavia no se ejecuta de forma directa.", 400)
    return respuesta_exitosa(resultado)


@bp.get("/pipelines")
@jwt_required()
def listar_pipelines():
    pipelines = Pipeline.query.order_by(Pipeline.creado_en.desc()).all()
    return respuesta_exitosa({"elementos": [serializar_pipeline(pipeline) for pipeline in pipelines]})


@bp.post("/pipelines")
@requiere_roles("qa", "devops")
def crear_pipeline_api():
    return respuesta_exitosa(serializar_pipeline(crear_pipeline(obtener_json())), 201)


@bp.get("/pipelines/<uuid:pipeline_id>")
@jwt_required()
def obtener_pipeline(pipeline_id: UUID):
    return respuesta_exitosa(serializar_pipeline(Pipeline.query.get_or_404(pipeline_id)))


@bp.patch("/pipelines/<uuid:pipeline_id>")
@requiere_roles("qa", "devops")
def actualizar_pipeline_api(pipeline_id: UUID):
    return respuesta_exitosa(serializar_pipeline(actualizar_pipeline(pipeline_id, obtener_json())))


@bp.post("/pipelines/<uuid:pipeline_id>/ejecutar")
@requiere_roles("qa", "devops")
def ejecutar_pipeline_api(pipeline_id: UUID):
    datos = obtener_json()
    ejecucion = encolar_ejecucion(pipeline_id, datos["entorno_id"], "manual")
    if datos.get("procesar_ahora", False):
        procesar_ejecucion(ejecucion)
    return respuesta_exitosa(serializar_ejecucion(ejecucion), 201)


@bp.get("/programaciones")
@jwt_required()
def listar_programaciones():
    programaciones = Programacion.query.all()
    return respuesta_exitosa({"elementos": [serializar_programacion(programacion) for programacion in programaciones]})


@bp.post("/programaciones")
@requiere_roles("devops")
def crear_programacion_api():
    return respuesta_exitosa(serializar_programacion(crear_programacion(obtener_json())), 201)


@bp.patch("/programaciones/<uuid:programacion_id>")
@requiere_roles("devops")
def actualizar_programacion_api(programacion_id: UUID):
    return respuesta_exitosa(serializar_programacion(actualizar_programacion(programacion_id, obtener_json())))


@bp.post("/programaciones/previsualizar")
@requiere_roles("devops")
def previsualizar_programacion():
    datos = obtener_json()
    siguiente = calcular_siguiente_programacion(datos["tipo_frecuencia"], datos.get("configuracion_frecuencia", {}), zona_horaria=datos.get("zona_horaria", current_app.config.get("ZONA_HORARIA_APLICACION", "America/Guatemala")))
    return respuesta_exitosa({"siguiente_ejecucion": iso_utc(siguiente)})


@bp.get("/ejecuciones")
@jwt_required()
def listar_ejecuciones():
    ejecuciones = Ejecucion.query.order_by(Ejecucion.fecha_encolado.desc()).limit(100).all()
    return respuesta_exitosa({"elementos": [serializar_ejecucion(ejecucion) for ejecucion in ejecuciones]})


@bp.get("/ejecuciones/<uuid:ejecucion_id>")
@jwt_required()
def obtener_ejecucion(ejecucion_id: UUID):
    return respuesta_exitosa(serializar_ejecucion(Ejecucion.query.get_or_404(ejecucion_id)))


@bp.post("/ejecuciones/<uuid:ejecucion_id>/informe")
@requiere_roles("qa", "devops", "responsable")
def generar_informe_ejecucion(ejecucion_id: UUID):
    informe = obtener_o_generar_informe(ejecucion_id, regenerar=bool(obtener_json().get("regenerar")))
    return respuesta_exitosa({
        "id": informe.id,
        "ejecucion_id": informe.ejecucion_id,
        "nombre_archivo": informe.nombre_archivo,
        "tamano_bytes": informe.tamano_bytes,
        "hash_sha256": informe.hash_sha256,
        "generado_en": informe.generado_en,
        "zona_horaria": informe.zona_horaria,
        "version": informe.version,
        "url": f"/api/ejecuciones/{ejecucion_id}/informe/pdf",
    }, 201)


@bp.get("/ejecuciones/<uuid:ejecucion_id>/informe/pdf")
@jwt_required()
def ver_informe_ejecucion(ejecucion_id: UUID):
    informe = obtener_o_generar_informe(ejecucion_id)
    ruta = Path(current_app.config["RUTA_INFORMES"]) / informe.ruta_relativa
    if not ruta.exists():
        return respuesta_error("informe_no_disponible", "El informe solicitado no esta disponible.", 404)
    descargar = request.args.get("descargar") == "1"
    return send_file(ruta.resolve(), mimetype=informe.tipo_contenido, download_name=informe.nombre_archivo, as_attachment=descargar)


@bp.post("/ejecuciones/<uuid:ejecucion_id>/revision")
@requiere_roles("qa", "devops", "responsable")
def revisar_ejecucion(ejecucion_id: UUID):
    Ejecucion.query.get_or_404(ejecucion_id)
    datos = obtener_json()
    if datos.get("clasificacion") not in {"confirmada", "falso_positivo", "falso_negativo", "requiere_analisis"}:
        return respuesta_error("clasificacion_invalida", "La clasificacion indicada no es valida.", 400)
    revision = RevisionEjecucion.query.filter_by(ejecucion_id=ejecucion_id).first()
    if revision is None:
        revision = RevisionEjecucion(ejecucion_id=ejecucion_id, clasificacion=datos["clasificacion"], revisado_por=UUID(get_jwt_identity()))
        db.session.add(revision)
    revision.clasificacion = datos["clasificacion"]
    revision.comentario = datos.get("comentario", "")
    revision.revisado_por = UUID(get_jwt_identity())
    db.session.commit()
    return respuesta_exitosa(serializar_revision_ejecucion(revision))


@bp.post("/resultados-paso/<uuid:resultado_id>/revision")
@requiere_roles("qa", "devops", "responsable")
def revisar_resultado_paso(resultado_id: UUID):
    ResultadoPaso.query.get_or_404(resultado_id)
    datos = obtener_json()
    if datos.get("clasificacion") not in {"confirmado", "falso_positivo", "falso_negativo", "no_aplica"}:
        return respuesta_error("clasificacion_invalida", "La clasificacion indicada no es valida.", 400)
    revision = RevisionPaso.query.filter_by(resultado_paso_id=resultado_id).first()
    if revision is None:
        revision = RevisionPaso(resultado_paso_id=resultado_id, clasificacion=datos["clasificacion"], revisado_por=UUID(get_jwt_identity()))
        db.session.add(revision)
    revision.clasificacion = datos["clasificacion"]
    revision.comentario = datos.get("comentario", "")
    revision.revisado_por = UUID(get_jwt_identity())
    db.session.commit()
    return respuesta_exitosa(serializar_revision_paso(revision))


@bp.post("/ejecuciones/<uuid:ejecucion_id>/cancelar")
@requiere_roles("qa", "devops")
def cancelar_ejecucion(ejecucion_id: UUID):
    ejecucion = Ejecucion.query.get_or_404(ejecucion_id)
    if ejecucion.estado in {"en_cola", "en_ejecucion"}:
        ejecucion.estado = "cancelada"
        db.session.commit()
    return respuesta_exitosa(serializar_ejecucion(ejecucion))


@bp.get("/evidencias/<uuid:evidencia_id>")
@jwt_required()
def descargar_evidencia(evidencia_id: UUID):
    evidencia = Evidencia.query.get_or_404(evidencia_id)
    ruta = Path(current_app.config["RUTA_EVIDENCIAS"]) / evidencia.ruta_relativa
    if not ruta.exists():
        return respuesta_error("evidencia_no_disponible", "La evidencia solicitada no esta disponible.", 404)
    return send_file(ruta, mimetype=evidencia.tipo_contenido, download_name=evidencia.nombre_archivo, as_attachment=True)


@bp.get("/alertas")
@jwt_required()
def listar_alertas():
    alertas = Alerta.query.order_by(Alerta.fecha_deteccion.desc()).all()
    return respuesta_exitosa({"elementos": [serializar_alerta(alerta) for alerta in alertas]})


@bp.patch("/alertas/<uuid:alerta_id>/revisar")
@requiere_roles("qa", "devops", "responsable")
def revisar_alerta(alerta_id: UUID):
    alerta = Alerta.query.get_or_404(alerta_id)
    datos = obtener_json()
    if datos.get("clasificacion_manual") not in {"pendiente", "confirmada", "falso_positivo"}:
        return respuesta_error("clasificacion_invalida", "La clasificacion indicada no es valida.", 400)
    alerta.clasificacion_manual = datos["clasificacion_manual"]
    alerta.estado_revision = "revisada"
    alerta.observacion_revision = datos.get("observacion_revision", "")
    alerta.fecha_reconocimiento = ahora_utc()
    alerta.reconocida_por = UUID(get_jwt_identity())
    db.session.commit()
    return respuesta_exitosa(serializar_alerta(alerta))
