import socket
import time
from urllib.parse import urljoin
from uuid import UUID

import requests
from flask import current_app
from sqlalchemy import create_engine, text

from aplicacion.modelos import Secreto
from aplicacion.seguridad.cifrado import descifrar_valor
from aplicacion.servicios.validaciones import ConfiguracionInvalida, validar_consulta_lectura
from aplicacion.utilidades.sanitizacion import sanitizar_texto


def _fallo_servicio_indisponible(exc: Exception, esperado: str, objetivo: dict, inicio: float) -> dict:
    return {
        "estado": "fallida",
        "esperado": esperado,
        "obtenido": "Servicio no disponible",
        "mensaje": "Servicio no disponible detectado por monitor",
        "duracion_milisegundos": int((time.perf_counter() - inicio) * 1000),
        "datos": {
            "clasificacion": "servicio_indisponible",
            "error_sanitizado": sanitizar_texto(exc),
            "resultado_conexion": "fallida",
            **objetivo,
        },
    }


def ejecutar_monitor_http(url_base: str, configuracion: dict, verificar_tls: bool, tiempo_entorno: int) -> dict:
    ruta = configuracion.get("ruta") or configuracion.get("url") or "/"
    url = ruta if ruta.startswith(("http://", "https://")) else urljoin(url_base.rstrip("/") + "/", ruta.lstrip("/"))
    metodo = configuracion.get("metodo", "GET").upper()
    if metodo not in {"GET", "HEAD"}:
        raise ConfiguracionInvalida("El monitor HTTP solo permite GET o HEAD.")
    estados_esperados = configuracion.get("estados_esperados") or [configuracion.get("estado_esperado", 200)]
    inicio = time.perf_counter()
    try:
        respuesta = requests.request(metodo, url, timeout=tiempo_entorno, verify=verificar_tls)
    except requests.RequestException as exc:
        return _fallo_servicio_indisponible(exc, f"Estados {estados_esperados}", {"url": url, "metodo": metodo}, inicio)
    duracion = int((time.perf_counter() - inicio) * 1000)
    texto_esperado = configuracion.get("texto_esperado")
    estado_correcto = respuesta.status_code in estados_esperados
    texto_correcto = texto_esperado is None or texto_esperado in respuesta.text
    return {
        "estado": "exitosa" if estado_correcto and texto_correcto else "fallida",
        "esperado": f"Estados {estados_esperados}",
        "obtenido": f"Estado {respuesta.status_code}",
        "mensaje": "Monitor HTTP ejecutado",
        "duracion_milisegundos": duracion,
        "datos": {
            "url": url,
            "metodo": metodo,
            "estado_http": respuesta.status_code,
            "estados_esperados": estados_esperados,
            "validacion_contenido": "no_evaluada" if texto_esperado is None else ("exitosa" if texto_correcto else "fallida"),
            "clasificacion": "disponible" if estado_correcto and texto_correcto else "respuesta_no_esperada",
            "tiempo_respuesta_milisegundos": duracion,
            "fragmento_respuesta": sanitizar_texto(respuesta.text, 300),
        },
    }


def ejecutar_monitor_api(configuracion: dict) -> dict:
    metodo = configuracion.get("metodo", "GET").upper()
    if metodo not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}:
        raise ConfiguracionInvalida("Metodo HTTP no permitido para API.")
    estados_esperados = configuracion.get("estados_esperados", [200])
    inicio = time.perf_counter()
    try:
        respuesta = requests.request(
            metodo,
            configuracion["url"],
            headers=configuracion.get("encabezados", {}),
            params=configuracion.get("parametros", {}),
            json=configuracion.get("cuerpo_json"),
            timeout=configuracion.get("tiempo_espera", 15),
        )
    except requests.RequestException as exc:
        return _fallo_servicio_indisponible(exc, f"Estados {estados_esperados}", {"url": configuracion["url"], "metodo": metodo}, inicio)
    duracion = int((time.perf_counter() - inicio) * 1000)
    texto_esperado = configuracion.get("texto_esperado")
    estado_correcto = respuesta.status_code in estados_esperados
    texto_correcto = texto_esperado is None or texto_esperado in respuesta.text
    return {
        "estado": "exitosa" if estado_correcto and texto_correcto else "fallida",
        "esperado": f"Estados {estados_esperados}",
        "obtenido": f"Estado {respuesta.status_code}",
        "mensaje": "Monitor API ejecutado",
        "duracion_milisegundos": duracion,
        "datos": {
            "url": configuracion["url"],
            "metodo": metodo,
            "estado_http": respuesta.status_code,
            "estados_esperados": estados_esperados,
            "validacion_contenido": "no_evaluada" if texto_esperado is None else ("exitosa" if texto_correcto else "fallida"),
            "clasificacion": "disponible" if estado_correcto and texto_correcto else "respuesta_no_esperada",
            "tiempo_respuesta_milisegundos": duracion,
            "fragmento_respuesta": sanitizar_texto(respuesta.text, 300),
        },
    }


def ejecutar_monitor_tcp(configuracion: dict) -> dict:
    inicio = time.perf_counter()
    try:
        with socket.create_connection((configuracion["host"], int(configuracion["puerto"])), timeout=configuracion.get("tiempo_espera", 5)):
            duracion = int((time.perf_counter() - inicio) * 1000)
    except OSError as exc:
        return _fallo_servicio_indisponible(
            exc,
            "Conexion TCP exitosa",
            {"host": configuracion["host"], "puerto": configuracion["puerto"]},
            inicio,
        )
    return {
        "estado": "exitosa",
        "esperado": "Conexion TCP exitosa",
        "obtenido": "Conexion TCP exitosa",
        "mensaje": "Monitor TCP ejecutado",
        "duracion_milisegundos": duracion,
        "datos": {"host": configuracion["host"], "puerto": configuracion["puerto"], "resultado_conexion": "exitosa", "tiempo_respuesta_milisegundos": duracion},
    }


def ejecutar_monitor_base_datos(configuracion: dict, cadena_conexion: str) -> dict:
    consulta = configuracion.get("consulta") or "SELECT 1"
    validar_consulta_lectura(consulta)
    inicio = time.perf_counter()
    motor = create_engine(cadena_conexion, pool_pre_ping=True)
    with motor.connect() as conexion:
        conexion.execute(text(consulta)).first()
    duracion = int((time.perf_counter() - inicio) * 1000)
    return {
        "estado": "exitosa",
        "esperado": "Consulta de lectura exitosa",
        "obtenido": "Consulta de lectura exitosa",
        "mensaje": "Monitor de base de datos ejecutado",
        "duracion_milisegundos": duracion,
        "datos": {"consulta": consulta, "resultado_conexion": "exitosa", "tiempo_respuesta_milisegundos": duracion},
    }


def resolver_cadena_conexion_base_datos(configuracion: dict) -> str:
    if configuracion.get("cadena_conexion"):
        return configuracion["cadena_conexion"]
    secreto_id = configuracion.get("secreto_cadena_conexion_id")
    if secreto_id:
        secreto = Secreto.query.get_or_404(UUID(str(secreto_id)))
        return descifrar_valor(current_app.config["CLAVE_CIFRADO_SECRETOS"], secreto.valor_cifrado)
    raise ConfiguracionInvalida("El monitor de base de datos requiere cadena de conexion o secreto asociado.")
