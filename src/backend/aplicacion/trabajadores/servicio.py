import logging
from datetime import datetime, timezone
from pathlib import Path
import re
from uuid import UUID

from flask import current_app

from aplicacion.automatizacion.selenium_servicio import ejecutar_caso_selenium
from aplicacion.evidencias.servicio import registrar_archivo_evidencia
from aplicacion.extensiones import db
from aplicacion.modelos import Alerta, CasoPrueba, Ejecucion, Entorno, Monitor, ResultadoPaso
from aplicacion.monitoreo.servicio import ejecutar_monitor_api, ejecutar_monitor_base_datos, ejecutar_monitor_http, ejecutar_monitor_tcp, resolver_cadena_conexion_base_datos
from aplicacion.notificaciones.servicio import enviar_notificaciones_fallo
from aplicacion.utilidades.sanitizacion import sanitizar_diccionario, sanitizar_texto


logger = logging.getLogger("trabajador_qa")


def diferencia_milisegundos(inicio: datetime, fin: datetime) -> int:
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=timezone.utc)
    if fin.tzinfo is None:
        fin = fin.replace(tzinfo=timezone.utc)
    return int((fin - inicio).total_seconds() * 1000)


def reclamar_ejecucion(trabajador_id: str) -> Ejecucion | None:
    ejecucion = Ejecucion.query.filter_by(estado="en_cola").order_by(Ejecucion.fecha_encolado.asc()).first()
    if ejecucion is None:
        return None
    ejecucion.estado = "en_ejecucion"
    ejecucion.fecha_inicio = datetime.now(timezone.utc)
    ejecucion.trabajador_id = trabajador_id
    db.session.commit()
    logger.info("ejecucion_reclamada id=%s pipeline_id=%s trabajador_id=%s", ejecucion.id, ejecucion.pipeline_id, trabajador_id)
    return ejecucion


def guardar_resultado(ejecucion: Ejecucion, paso_pipeline_id: UUID | None, tipo: str, datos: dict, paso_caso_prueba_id: UUID | None = None) -> ResultadoPaso:
    fin = datetime.now(timezone.utc)
    resultado = ResultadoPaso(
        ejecucion_id=ejecucion.id,
        paso_pipeline_id=paso_pipeline_id,
        paso_caso_prueba_id=paso_caso_prueba_id,
        tipo=tipo,
        estado=datos["estado"],
        esperado=sanitizar_texto(datos.get("esperado", "")),
        obtenido=sanitizar_texto(datos.get("obtenido", "")),
        mensaje=sanitizar_texto(datos.get("mensaje", "")),
        fecha_fin=fin,
        duracion_milisegundos=datos.get("duracion_milisegundos"),
        datos_tecnicos_sanitizados=sanitizar_diccionario(datos.get("datos", {})),
    )
    db.session.add(resultado)
    db.session.flush()
    if resultado.estado != "exitosa" and ejecucion.fecha_deteccion_primer_fallo is None:
        ejecucion.fecha_deteccion_primer_fallo = fin
    return resultado


def guardar_error_tecnico_paso(
    ejecucion: Ejecucion,
    paso_pipeline_id: UUID | None,
    tipo: str,
    exc: Exception,
    datos_extra: dict | None = None,
) -> ResultadoPaso:
    datos = {
        "estado": "error_tecnico",
        "esperado": "Paso ejecutado sin excepciones tecnicas",
        "obtenido": "Excepcion tecnica controlada",
        "mensaje": sanitizar_texto(exc),
        "datos": {"clasificacion": "error_tecnico", **(datos_extra or {})},
    }
    return guardar_resultado(ejecucion, paso_pipeline_id, tipo, datos)


def ejecutar_paso_monitor(ejecucion: Ejecucion, entorno: Entorno, paso_pipeline) -> ResultadoPaso:
    monitor = Monitor.query.get(paso_pipeline.monitor_id)
    if monitor is None:
        exc = RuntimeError("Monitor no encontrado")
        return guardar_error_tecnico_paso(ejecucion, paso_pipeline.id, "monitor", exc, {"paso_pipeline_id": str(paso_pipeline.id)})
    try:
        if monitor.tipo == "http":
            datos = ejecutar_monitor_http(entorno.url_base, monitor.configuracion, entorno.verificar_certificado_tls, entorno.tiempo_espera_segundos)
        elif monitor.tipo == "api":
            datos = ejecutar_monitor_api(monitor.configuracion)
        elif monitor.tipo == "tcp":
            datos = ejecutar_monitor_tcp(monitor.configuracion)
        elif monitor.tipo == "base_datos":
            datos = ejecutar_monitor_base_datos(monitor.configuracion, resolver_cadena_conexion_base_datos(monitor.configuracion))
        else:
            datos = {"estado": "error_tecnico", "esperado": "Monitor soportado", "obtenido": monitor.tipo, "mensaje": "Tipo de monitor pendiente", "datos": {}}
        datos.setdefault("datos", {})
        datos["datos"].update({"monitor": monitor.nombre, "tipo_monitor": monitor.tipo, "paso_pipeline_id": str(paso_pipeline.id)})
        return guardar_resultado(ejecucion, paso_pipeline.id, f"monitor_{monitor.tipo}", datos)
    except Exception as exc:
        logger.exception("error_tecnico_monitor ejecucion_id=%s paso_pipeline_id=%s monitor_id=%s", ejecucion.id, paso_pipeline.id, monitor.id)
        return guardar_error_tecnico_paso(
            ejecucion,
            paso_pipeline.id,
            f"monitor_{monitor.tipo}",
            exc,
            {"monitor": monitor.nombre, "tipo_monitor": monitor.tipo, "paso_pipeline_id": str(paso_pipeline.id)},
        )


def ejecutar_paso_caso(ejecucion: Ejecucion, entorno: Entorno, paso_pipeline) -> list[ResultadoPaso]:
    caso = CasoPrueba.query.get(paso_pipeline.caso_prueba_id)
    if caso is None:
        raise RuntimeError("Caso de prueba no encontrado")
    resultados = []
    try:
        datos_pasos = ejecutar_caso_selenium(entorno.url_base, caso.pasos, entorno.tiempo_espera_segundos, caso.proyecto_id)
    except Exception as exc:
        logger.exception("error_tecnico_caso ejecucion_id=%s paso_pipeline_id=%s caso_id=%s", ejecucion.id, paso_pipeline.id, caso.id)
        return [
            guardar_error_tecnico_paso(
                ejecucion,
                paso_pipeline.id,
                "caso_prueba",
                exc,
                {"caso_prueba": caso.nombre, "paso_pipeline_id": str(paso_pipeline.id)},
            )
        ]
    for indice, datos in enumerate(datos_pasos, start=1):
        paso = datos["paso"]
        resultado = guardar_resultado(
            ejecucion,
            paso_pipeline.id,
            "caso_prueba",
            datos,
            paso_caso_prueba_id=paso.id,
        )
        if datos.get("captura"):
            nombre = datos.get("nombre_evidencia") or f"captura_{indice}"
            nombre = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(nombre)).strip("._") or f"captura_{indice}"
            nombre_archivo = Path(nombre).name
            if not nombre_archivo.lower().endswith(".png"):
                nombre_archivo = f"{nombre_archivo}.png"
            evidencia = registrar_archivo_evidencia(ejecucion.id, resultado.id, nombre_archivo, datos["captura"])
            resultado.datos_tecnicos_sanitizados = sanitizar_diccionario({
                **(resultado.datos_tecnicos_sanitizados or {}),
                "evidencia": {
                    "id": str(evidencia.id),
                    "nombre_archivo": evidencia.nombre_archivo,
                    "almacenamiento": "registrado",
                    "resultado_paso_id": str(resultado.id),
                },
            })
        resultados.append(resultado)
    return resultados


def finalizar_ejecucion(ejecucion: Ejecucion) -> None:
    fin = datetime.now(timezone.utc)
    ejecucion.fecha_fin = fin
    ejecucion.duracion_milisegundos = diferencia_milisegundos(ejecucion.fecha_inicio or ejecucion.fecha_encolado, fin)
    estados = {resultado.estado for resultado in ejecucion.resultados}
    if "error_tecnico" in estados:
        ejecucion.estado = "error_tecnico"
    elif "fallida" in estados:
        ejecucion.estado = "fallida"
    else:
        ejecucion.estado = "exitosa"
    if ejecucion.estado in {"fallida", "error_tecnico"}:
        db.session.add(Alerta(ejecucion_id=ejecucion.id, tipo="pipeline", severidad="alta" if ejecucion.estado == "error_tecnico" else "media"))


def procesar_ejecucion(ejecucion: Ejecucion) -> Ejecucion:
    try:
        entorno = Entorno.query.get_or_404(ejecucion.entorno_id)
        logger.info("ejecucion_inicio id=%s pipeline_id=%s entorno_id=%s", ejecucion.id, ejecucion.pipeline_id, ejecucion.entorno_id)
        for paso_pipeline in ejecucion.pipeline.pasos:
            if ejecucion.estado == "cancelada":
                break
            if paso_pipeline.tipo == "monitor":
                resultado = ejecutar_paso_monitor(ejecucion, entorno, paso_pipeline)
                db.session.flush()
                if resultado.estado != "exitosa" and not paso_pipeline.continuar_si_falla and ejecucion.pipeline.detener_ante_fallo:
                    break
            elif paso_pipeline.tipo == "caso_prueba":
                resultados = ejecutar_paso_caso(ejecucion, entorno, paso_pipeline)
                db.session.flush()
                if any(resultado.estado != "exitosa" for resultado in resultados) and not paso_pipeline.continuar_si_falla and ejecucion.pipeline.detener_ante_fallo:
                    break
        finalizar_ejecucion(ejecucion)
        logger.info("ejecucion_fin id=%s estado=%s resultados=%s", ejecucion.id, ejecucion.estado, len(ejecucion.resultados))
    except Exception as exc:
        logger.exception("error_tecnico_ejecucion id=%s", ejecucion.id)
        if not ejecucion.resultados:
            guardar_error_tecnico_paso(
                ejecucion,
                None,
                "inicializacion",
                exc,
                {"fase": "procesar_ejecucion", "pipeline_id": str(ejecucion.pipeline_id), "entorno_id": str(ejecucion.entorno_id)},
            )
        ejecucion.estado = "error_tecnico"
        ejecucion.error_tecnico = sanitizar_texto(exc)
        ejecucion.fecha_fin = datetime.now(timezone.utc)
        if ejecucion.fecha_inicio:
            ejecucion.duracion_milisegundos = diferencia_milisegundos(ejecucion.fecha_inicio, ejecucion.fecha_fin)
        db.session.add(Alerta(ejecucion_id=ejecucion.id, tipo="error_tecnico", severidad="alta"))
    # Guardar el resultado antes de generar el informe o contactar servicios externos.
    db.session.commit()
    try:
        enviar_notificaciones_fallo(ejecucion)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("error_notificacion_ejecucion id=%s", ejecucion.id)
    return ejecucion


def procesar_siguiente_ejecucion(trabajador_id: str) -> Ejecucion | None:
    ejecucion = reclamar_ejecucion(trabajador_id)
    if ejecucion is None:
        return None
    return procesar_ejecucion(ejecucion)
