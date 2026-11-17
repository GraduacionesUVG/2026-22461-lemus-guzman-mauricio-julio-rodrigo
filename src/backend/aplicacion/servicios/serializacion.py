from aplicacion.modelos import Alerta
from aplicacion.modelos import CanalNotificacion
from aplicacion.modelos import CasoPrueba
from aplicacion.modelos import Entorno
from aplicacion.modelos import Evidencia
from aplicacion.modelos import Ejecucion
from aplicacion.modelos import ModuloObjetivo
from aplicacion.modelos import Monitor
from aplicacion.modelos import PasoCasoPrueba
from aplicacion.modelos import PasoPipeline
from aplicacion.modelos import Pipeline
from aplicacion.modelos import Programacion
from aplicacion.modelos import Proyecto
from aplicacion.modelos import ResultadoPaso
from aplicacion.modelos import RevisionEjecucion
from aplicacion.modelos import RevisionPaso
from aplicacion.modelos import Secreto
from aplicacion.modelos import Usuario
from aplicacion.utilidades.respuestas import convertir_diccionario


def serializar_usuario(usuario: Usuario) -> dict:
    return convertir_diccionario({
        "id": usuario.id,
        "nombre": usuario.nombre,
        "correo": usuario.correo,
        "activo": usuario.activo,
        "roles": [rol.nombre for rol in usuario.roles],
        "ultimo_acceso": usuario.ultimo_acceso,
        "tour_completado": usuario.tour_completado,
        "creado_en": usuario.creado_en,
    })


def serializar_proyecto(proyecto: Proyecto) -> dict:
    return convertir_diccionario({
        "id": proyecto.id,
        "nombre": proyecto.nombre,
        "descripcion": proyecto.descripcion,
        "tecnologia_referencial": proyecto.tecnologia_referencial,
        "responsable": proyecto.responsable,
        "activo": proyecto.activo,
        "creado_en": proyecto.creado_en,
        "actualizado_en": proyecto.actualizado_en,
    })


def serializar_modulo(modulo: ModuloObjetivo) -> dict:
    return convertir_diccionario({
        "id": modulo.id,
        "proyecto_id": modulo.proyecto_id,
        "nombre": modulo.nombre,
        "descripcion": modulo.descripcion,
        "critico": modulo.critico,
        "activo": modulo.activo,
    })


def serializar_entorno(entorno: Entorno) -> dict:
    return convertir_diccionario({
        "id": entorno.id,
        "proyecto_id": entorno.proyecto_id,
        "nombre": entorno.nombre,
        "url_base": entorno.url_base,
        "zona_horaria": entorno.zona_horaria,
        "verificar_certificado_tls": entorno.verificar_certificado_tls,
        "tiempo_espera_segundos": entorno.tiempo_espera_segundos,
        "activo": entorno.activo,
    })


def serializar_secreto(secreto: Secreto) -> dict:
    return convertir_diccionario({
        "id": secreto.id,
        "proyecto_id": secreto.proyecto_id,
        "entorno_id": secreto.entorno_id,
        "nombre": secreto.nombre,
        "tipo": secreto.tipo,
        "creado_en": secreto.creado_en,
        "actualizado_en": secreto.actualizado_en,
    })


def serializar_canal_notificacion(canal: CanalNotificacion) -> dict:
    return convertir_diccionario({
        "id": canal.id,
        "proyecto_id": canal.proyecto_id,
        "nombre": canal.nombre,
        "tipo": canal.tipo,
        "activo": canal.activo,
    })


def serializar_paso_caso(paso: PasoCasoPrueba) -> dict:
    return convertir_diccionario({
        "id": paso.id,
        "orden": paso.orden,
        "tipo": paso.tipo,
        "nombre": paso.nombre,
        "configuracion": paso.configuracion,
        "continuar_si_falla": paso.continuar_si_falla,
        "capturar_evidencia": paso.capturar_evidencia,
    })


def serializar_caso(caso: CasoPrueba) -> dict:
    return convertir_diccionario({
        "id": caso.id,
        "proyecto_id": caso.proyecto_id,
        "modulo_objetivo_id": caso.modulo_objetivo_id,
        "nombre": caso.nombre,
        "descripcion": caso.descripcion,
        "prioridad": caso.prioridad,
        "activo": caso.activo,
        "requiere_revision_humana": caso.requiere_revision_humana,
        "version": caso.version,
        "pasos": [serializar_paso_caso(paso) for paso in caso.pasos],
    })


def serializar_revision_paso(revision: RevisionPaso) -> dict:
    return convertir_diccionario({
        "id": revision.id,
        "resultado_paso_id": revision.resultado_paso_id,
        "clasificacion": revision.clasificacion,
        "comentario": revision.comentario,
        "revisado_por": revision.revisado_por,
        "creado_en": revision.creado_en,
        "actualizado_en": revision.actualizado_en,
    })


def serializar_revision_ejecucion(revision: RevisionEjecucion) -> dict:
    return convertir_diccionario({
        "id": revision.id,
        "ejecucion_id": revision.ejecucion_id,
        "clasificacion": revision.clasificacion,
        "comentario": revision.comentario,
        "revisado_por": revision.revisado_por,
        "creado_en": revision.creado_en,
        "actualizado_en": revision.actualizado_en,
    })


def serializar_monitor(monitor: Monitor) -> dict:
    return convertir_diccionario({
        "id": monitor.id,
        "proyecto_id": monitor.proyecto_id,
        "entorno_id": monitor.entorno_id,
        "nombre": monitor.nombre,
        "tipo": monitor.tipo,
        "configuracion": monitor.configuracion,
        "intervalo_recomendado_segundos": monitor.intervalo_recomendado_segundos,
        "activo": monitor.activo,
    })


def serializar_paso_pipeline(paso: PasoPipeline) -> dict:
    return convertir_diccionario({
        "id": paso.id,
        "orden": paso.orden,
        "tipo": paso.tipo,
        "caso_prueba_id": paso.caso_prueba_id,
        "monitor_id": paso.monitor_id,
        "nombre": paso.nombre,
        "continuar_si_falla": paso.continuar_si_falla,
        "configuracion": paso.configuracion,
    })


def serializar_pipeline(pipeline: Pipeline) -> dict:
    return convertir_diccionario({
        "id": pipeline.id,
        "proyecto_id": pipeline.proyecto_id,
        "nombre": pipeline.nombre,
        "descripcion": pipeline.descripcion,
        "activo": pipeline.activo,
        "detener_ante_fallo": pipeline.detener_ante_fallo,
        "version": pipeline.version,
        "pasos": [serializar_paso_pipeline(paso) for paso in pipeline.pasos],
    })


def serializar_programacion(programacion: Programacion) -> dict:
    return convertir_diccionario({
        "id": programacion.id,
        "pipeline_id": programacion.pipeline_id,
        "nombre": programacion.nombre,
        "tipo_frecuencia": programacion.tipo_frecuencia,
        "configuracion_frecuencia": programacion.configuracion_frecuencia,
        "zona_horaria": programacion.zona_horaria,
        "siguiente_ejecucion": programacion.siguiente_ejecucion,
        "activo": programacion.activo,
    })


def obtener_contexto_resultado(resultado: ResultadoPaso) -> dict:
    paso_pipeline = PasoPipeline.query.get(resultado.paso_pipeline_id) if resultado.paso_pipeline_id else None
    paso_caso = PasoCasoPrueba.query.get(resultado.paso_caso_prueba_id) if resultado.paso_caso_prueba_id else None
    caso = CasoPrueba.query.get(paso_caso.caso_prueba_id) if paso_caso else None
    monitor = Monitor.query.get(paso_pipeline.monitor_id) if paso_pipeline and paso_pipeline.monitor_id else None
    return convertir_diccionario({
        "paso_pipeline": paso_pipeline.nombre if paso_pipeline else None,
        "orden_pipeline": paso_pipeline.orden if paso_pipeline else None,
        "tipo_pipeline": paso_pipeline.tipo if paso_pipeline else None,
        "caso_prueba": caso.nombre if caso else None,
        "paso_prueba": paso_caso.nombre if paso_caso else None,
        "orden_prueba": paso_caso.orden if paso_caso else None,
        "accion": paso_caso.tipo if paso_caso else resultado.tipo,
        "selector": (paso_caso.configuracion.get("selector") if paso_caso and isinstance(paso_caso.configuracion, dict) else None),
        "monitor": monitor.nombre if monitor else None,
    })


def serializar_resultado(resultado: ResultadoPaso) -> dict:
    revision = RevisionPaso.query.filter_by(resultado_paso_id=resultado.id).order_by(RevisionPaso.actualizado_en.desc()).first()
    return convertir_diccionario({
        "id": resultado.id,
        "paso_caso_prueba_id": resultado.paso_caso_prueba_id,
        "paso_pipeline_id": resultado.paso_pipeline_id,
        "contexto": obtener_contexto_resultado(resultado),
        "tipo": resultado.tipo,
        "estado": resultado.estado,
        "esperado": resultado.esperado,
        "obtenido": resultado.obtenido,
        "mensaje": resultado.mensaje,
        "fecha_inicio": resultado.fecha_inicio,
        "fecha_fin": resultado.fecha_fin,
        "duracion_milisegundos": resultado.duracion_milisegundos,
        "datos_tecnicos_sanitizados": resultado.datos_tecnicos_sanitizados,
        "revision_humana": serializar_revision_paso(revision) if revision else None,
    })


def serializar_alerta_resumen(alerta: Alerta) -> dict:
    return convertir_diccionario({
        "id": alerta.id,
        "ejecucion_id": alerta.ejecucion_id,
        "tipo": alerta.tipo,
        "severidad": alerta.severidad,
        "estado_revision": alerta.estado_revision,
        "fecha_deteccion": alerta.fecha_deteccion,
        "fecha_reconocimiento": alerta.fecha_reconocimiento,
        "clasificacion_manual": alerta.clasificacion_manual,
        "observacion_revision": alerta.observacion_revision,
    })


def serializar_ejecucion(ejecucion: Ejecucion) -> dict:
    evidencias = Evidencia.query.filter_by(ejecucion_id=ejecucion.id).all()
    alertas = Alerta.query.filter_by(ejecucion_id=ejecucion.id).order_by(Alerta.fecha_deteccion.asc()).all()
    revision = RevisionEjecucion.query.filter_by(ejecucion_id=ejecucion.id).order_by(RevisionEjecucion.actualizado_en.desc()).first()
    pipeline = Pipeline.query.get(ejecucion.pipeline_id)
    entorno = Entorno.query.get(ejecucion.entorno_id)
    proyecto = Proyecto.query.get(pipeline.proyecto_id) if pipeline else None
    requiere_revision = any(
        resultado.paso_caso_prueba_id
        and CasoPrueba.query.join(PasoCasoPrueba, PasoCasoPrueba.caso_prueba_id == CasoPrueba.id)
        .filter(PasoCasoPrueba.id == resultado.paso_caso_prueba_id, CasoPrueba.requiere_revision_humana == True)
        .first()
        for resultado in ejecucion.resultados
    )
    return convertir_diccionario({
        "id": ejecucion.id,
        "pipeline_id": ejecucion.pipeline_id,
        "pipeline_nombre": pipeline.nombre if pipeline else None,
        "entorno_id": ejecucion.entorno_id,
        "entorno_nombre": entorno.nombre if entorno else None,
        "proyecto_id": proyecto.id if proyecto else None,
        "proyecto_nombre": proyecto.nombre if proyecto else None,
        "origen": ejecucion.origen,
        "estado": ejecucion.estado,
        "fecha_encolado": ejecucion.fecha_encolado,
        "fecha_inicio": ejecucion.fecha_inicio,
        "fecha_fin": ejecucion.fecha_fin,
        "fecha_deteccion_primer_fallo": ejecucion.fecha_deteccion_primer_fallo,
        "duracion_milisegundos": ejecucion.duracion_milisegundos,
        "error_tecnico": ejecucion.error_tecnico,
        "requiere_revision_humana": requiere_revision,
        "revision_humana": serializar_revision_ejecucion(revision) if revision else None,
        "resultados": [serializar_resultado(resultado) for resultado in ejecucion.resultados],
        "evidencias": [serializar_evidencia(evidencia) for evidencia in evidencias],
        "alertas": [serializar_alerta_resumen(alerta) for alerta in alertas],
    })


def serializar_evidencia(evidencia: Evidencia) -> dict:
    return convertir_diccionario({
        "id": evidencia.id,
        "ejecucion_id": evidencia.ejecucion_id,
        "resultado_paso_id": evidencia.resultado_paso_id,
        "tipo": evidencia.tipo,
        "nombre_archivo": evidencia.nombre_archivo,
        "tipo_contenido": evidencia.tipo_contenido,
        "tamano_bytes": evidencia.tamano_bytes,
        "hash_sha256": evidencia.hash_sha256,
        "creado_en": evidencia.creado_en,
    })


def serializar_alerta(alerta: Alerta) -> dict:
    ejecucion = Ejecucion.query.get(alerta.ejecucion_id)
    ejecucion_serializada = serializar_ejecucion(ejecucion) if ejecucion else None
    primer_resultado_fallido = None
    if ejecucion:
        primer_resultado_fallido = next((resultado for resultado in ejecucion.resultados if resultado.estado != "exitosa"), None)
    return convertir_diccionario({
        **serializar_alerta_resumen(alerta),
        "ejecucion": ejecucion_serializada,
        "resultado_principal": serializar_resultado(primer_resultado_fallido) if primer_resultado_fallido else None,
    })
