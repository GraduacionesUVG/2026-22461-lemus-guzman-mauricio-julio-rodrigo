
import smtplib
import json
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlparse

import requests
from flask import current_app

from aplicacion.auditoria.servicio import registrar_auditoria
from aplicacion.extensiones import db
from aplicacion.modelos import Alerta, CanalNotificacion, Ejecucion, Notificacion, Proyecto, ResultadoPaso
from aplicacion.seguridad.cifrado import cifrar_valor, descifrar_valor
from aplicacion.servicios.validaciones import ConfiguracionInvalida
from aplicacion.utilidades.presentacion import duracion_legible, etiqueta_estado, fecha_legible, recortar, resumir_diagnostico
from aplicacion.utilidades.sanitizacion import sanitizar_texto
from aplicacion.utilidades.tiempo import asegurar_utc


TITULO_NOTIFICACION = "Sistema Integral de Calidad Web | Ejecución finalizada"
COLORES_DISCORD = {"exitosa": 0x15803D, "fallida": 0xB42318, "error_tecnico": 0xD97706}
COLOR_DISCORD_NEUTRO = 0x64748B
LIMITE_VALOR_CAMPO_DISCORD = 200
LIMITE_DESCRIPCION_DISCORD = 1000


class CanalNotificacionInvalido(ConfiguracionInvalida):
    pass


def validar_configuracion_canal(tipo: str, configuracion: dict) -> None:
    if tipo == "webhook":
        if not configuracion.get("url"):
            raise CanalNotificacionInvalido("El webhook requiere URL.")

        metodo = configuracion.get("metodo", "POST").upper()

        if metodo not in {"POST", "PUT", "PATCH"}:
            raise CanalNotificacionInvalido(
                "El webhook solo permite POST, PUT o PATCH."
            )

    elif tipo == "correo":
        if not configuracion.get("destinatarios"):
            raise CanalNotificacionInvalido(
                "El correo requiere destinatarios."
            )
    else:
        raise CanalNotificacionInvalido(
            "Tipo de canal no permitido."
        )


def cifrar_configuracion_canal(configuracion: dict) -> str:
    texto = json.dumps(configuracion, ensure_ascii=False)

    return cifrar_valor(
        current_app.config["CLAVE_CIFRADO_SECRETOS"],
        texto
    )


def descifrar_configuracion_canal(canal: CanalNotificacion) -> dict:
    texto = descifrar_valor(
        current_app.config["CLAVE_CIFRADO_SECRETOS"],
        canal.configuracion_cifrada
    )
    return json.loads(texto)


def crear_canal_notificacion(proyecto_id, datos: dict) -> CanalNotificacion:
    tipo = datos["tipo"]
    configuracion = datos.get("configuracion", {})

    validar_configuracion_canal(tipo, configuracion)

    canal = CanalNotificacion(
        proyecto_id=proyecto_id,
        nombre=datos["nombre"],
        tipo=tipo,
        configuracion_cifrada=cifrar_configuracion_canal(configuracion),
        activo=datos.get("activo", True),
    )

    db.session.add(canal)

    registrar_auditoria(
        "crear",
        "canal_notificacion",
        datos={
            "nombre": canal.nombre,
            "tipo": canal.tipo
        }
    )

    db.session.commit()
    return canal


def actualizar_canal_notificacion(
    canal_id,
    datos: dict
) -> CanalNotificacion:

    canal = CanalNotificacion.query.get_or_404(canal_id)

    if "nombre" in datos:
        canal.nombre = datos["nombre"]

    if "activo" in datos:
        canal.activo = datos["activo"]

    if "configuracion" in datos:
        validar_configuracion_canal(
            canal.tipo,
            datos["configuracion"]
        )
        canal.configuracion_cifrada = cifrar_configuracion_canal(
            datos["configuracion"]
        )

    registrar_auditoria(
        "actualizar",
        "canal_notificacion",
        str(canal.id),
        {
            "nombre": canal.nombre,
            "activo": canal.activo
        }
    )

    db.session.commit()
    return canal


def plural(cantidad: int, singular: str, plural_texto: str) -> str:
    return f"{cantidad} {singular if cantidad == 1 else plural_texto}"


def con_punto_final(texto: str) -> str:
    texto = texto.strip()
    if not texto or texto[-1] in ".!?…":
        return texto
    return f"{texto}."


def nombre_paso_resultado(resultado: ResultadoPaso) -> str:
    from aplicacion.servicios.serializacion import obtener_contexto_resultado

    contexto = obtener_contexto_resultado(resultado)
    return contexto.get("paso_prueba") or contexto.get("paso_pipeline") or etiqueta_estado(resultado.tipo)


def datos_resumen_ejecucion(ejecucion: Ejecucion) -> dict:
    zona = current_app.config.get("ZONA_HORARIA_APLICACION", "America/Guatemala")
    resultados = list(ejecucion.resultados)
    pipeline = ejecucion.pipeline
    proyecto = Proyecto.query.get(pipeline.proyecto_id) if pipeline else None
    return {
        "proyecto": proyecto.nombre if proyecto else "No disponible",
        "pipeline": pipeline.nombre if pipeline else str(ejecucion.pipeline_id),
        "identificador": str(ejecucion.id)[:8],
        "estado": etiqueta_estado(ejecucion.estado),
        "inicio": fecha_legible(ejecucion.fecha_inicio, zona),
        "fin": fecha_legible(ejecucion.fecha_fin, zona),
        "duracion": duracion_legible(ejecucion.duracion_milisegundos),
        "exitosos": sum(1 for resultado in resultados if resultado.estado == "exitosa"),
        "fallidos": sum(1 for resultado in resultados if resultado.estado == "fallida"),
        "errores": sum(1 for resultado in resultados if resultado.estado == "error_tecnico"),
        "alertas": Alerta.query.filter_by(ejecucion_id=ejecucion.id).count(),
    }


def diagnostico_breve(ejecucion: Ejecucion, referencia: str) -> str:
    resultados = list(ejecucion.resultados)
    errores = [resultado for resultado in resultados if resultado.estado == "error_tecnico"]
    fallidos = [resultado for resultado in resultados if resultado.estado == "fallida"]
    if ejecucion.estado == "exitosa" and not errores and not fallidos:
        return "La ejecución finalizó sin pasos fallidos ni errores técnicos."
    if errores:
        principal = f"Se produjo un error técnico durante la acción '{nombre_paso_resultado(errores[0])}'."
        detalle = resumir_diagnostico(errores[0].mensaje)
    elif ejecucion.estado == "error_tecnico":
        principal = "Se produjo un error técnico durante la ejecución."
        detalle = resumir_diagnostico(ejecucion.error_tecnico)
    elif fallidos:
        verbo = "Se registró" if len(fallidos) == 1 else "Se registraron"
        principal = f"{verbo} {plural(len(fallidos), 'paso fallido', 'pasos fallidos')}; el primero corresponde a '{nombre_paso_resultado(fallidos[0])}'."
        detalle = resumir_diagnostico(fallidos[0].mensaje)
    else:
        principal = f"La ejecución finalizó con estado {etiqueta_estado(ejecucion.estado).lower()}."
        detalle = ""
    partes = [principal]
    if detalle:
        partes.append(f"Detalle: {con_punto_final(detalle)}")
    partes.append(referencia)
    return " ".join(partes)


def crear_mensaje_alerta_basico(ejecucion: Ejecucion) -> str:
    return "\n".join([
        TITULO_NOTIFICACION,
        f"Ejecución: {ejecucion.id}",
        f"Pipeline: {ejecucion.pipeline.nombre if ejecucion.pipeline else ejecucion.pipeline_id}",
        f"Estado final: {etiqueta_estado(ejecucion.estado)}",
        "Revise historial, evidencias y alertas en la plataforma.",
    ])


def crear_mensaje_alerta(ejecucion: Ejecucion) -> str:
    datos = datos_resumen_ejecucion(ejecucion)
    lineas = [
        TITULO_NOTIFICACION,
        f"Proyecto: {datos['proyecto']}",
        f"Pipeline: {datos['pipeline']}",
        f"Identificador: {datos['identificador']}",
        f"Estado final: {datos['estado']}",
        f"Inicio: {datos['inicio']}",
        f"Finalización: {datos['fin']}",
        f"Duración: {datos['duracion']}",
        f"Pasos exitosos: {datos['exitosos']} | Pasos fallidos: {datos['fallidos']} | Errores técnicos: {datos['errores']}",
        f"Alertas generadas: {datos['alertas']}",
        f"Diagnóstico: {diagnostico_breve(ejecucion, 'Revise historial, evidencias y alertas en la plataforma.')}",
    ]
    return "\n".join(lineas)


def crear_embed_discord(ejecucion: Ejecucion, con_adjunto: bool) -> dict:
    datos = datos_resumen_ejecucion(ejecucion)
    referencia = (
        "Consulte el informe adjunto para revisar el detalle."
        if con_adjunto
        else "Consulte el historial de la plataforma para revisar el detalle."
    )
    campos = [
        ("Proyecto", datos["proyecto"]),
        ("Pipeline", datos["pipeline"]),
        ("Identificador", f"`{datos['identificador']}`"),
        ("Estado final", datos["estado"]),
        ("Inicio", datos["inicio"]),
        ("Finalización", datos["fin"]),
        ("Duración", datos["duracion"]),
        ("Pasos exitosos", str(datos["exitosos"])),
        ("Pasos fallidos", str(datos["fallidos"])),
        ("Errores técnicos", str(datos["errores"])),
        ("Alertas generadas", str(datos["alertas"])),
    ]
    embed = {
        "title": TITULO_NOTIFICACION,
        "description": recortar(diagnostico_breve(ejecucion, referencia), LIMITE_DESCRIPCION_DISCORD),
        "color": COLORES_DISCORD.get(ejecucion.estado, COLOR_DISCORD_NEUTRO),
        "fields": [
            {"name": nombre, "value": recortar(valor or "No disponible", LIMITE_VALOR_CAMPO_DISCORD), "inline": True}
            for nombre, valor in campos
        ],
        "footer": {"text": "Sistema Integral de Calidad Web · Informe PDF adjunto" if con_adjunto else "Sistema Integral de Calidad Web"},
    }
    marca = asegurar_utc(ejecucion.fecha_fin)
    if marca:
        embed["timestamp"] = marca.isoformat()
    return embed


def crear_embed_discord_seguro(ejecucion: Ejecucion, con_adjunto: bool) -> dict | None:
    try:
        return crear_embed_discord(ejecucion, con_adjunto)
    except Exception:
        current_app.logger.exception("No se pudo construir el resumen de Discord para la ejecucion %s", ejecucion.id)
        return None


def registrar_notificacion(
    ejecucion: Ejecucion,
    canal: CanalNotificacion | None,
    estado: str,
    error: str = "",
    intentos: int = 1
) -> Notificacion:

    notificacion = Notificacion(
        ejecucion_id=ejecucion.id,
        canal_notificacion_id=canal.id if canal else None,
        estado=estado,
        fecha_envio=(
            datetime.now(timezone.utc)
            if estado == "enviada"
            else None
        ),
        intentos=intentos,
        error_sanitizado=sanitizar_texto(error),
    )

    db.session.add(notificacion)
    return notificacion


# ==========================================================
# WEBHOOKS: COMPATIBILIDAD CON DISCORD Y OTROS PROVEEDORES
# ==========================================================

def es_webhook_discord(url_webhook: str) -> bool:
    """
    Detecta webhooks oficiales de Discord por hostname
    y ruta. No utiliza coincidencias parciales del dominio.
    """
    url = urlparse(url_webhook)

    dominios_discord = {
        "discord.com",
        "discordapp.com",
        "canary.discord.com",
        "ptb.discord.com",
    }

    return (
        url.scheme == "https"
        and url.hostname in dominios_discord
        and url.path.startswith("/api/webhooks/")
    )


def construir_cuerpo_webhook(
    configuracion: dict,
    mensaje: str,
    embed: dict | None = None
) -> dict:
    """
    Construye el JSON compatible con el destino.

    Discord requiere 'content' o 'embeds'.
    Los webhooks genéricos conservan 'mensaje'.
    """

    if es_webhook_discord(configuracion["url"]):
        if embed:
            return {
                "embeds": [embed],
                "allowed_mentions": {
                    "parse": []
                }
            }
        return {
            "content": mensaje[:1900] or "Alerta del Sistema QA",
            "allowed_mentions": {
                "parse": []
            }
        }

    return {
        "mensaje": mensaje
    }


def solicitar_webhook(metodo: str, configuracion: dict, cuerpo: dict, adjunto_pdf: Path | None = None):
    if adjunto_pdf and es_webhook_discord(configuracion["url"]) and adjunto_pdf.exists():
        with adjunto_pdf.open("rb") as archivo:
            respuesta = requests.request(
                metodo,
                configuracion["url"],
                data={"payload_json": json.dumps(cuerpo, ensure_ascii=False)},
                files={"files[0]": (adjunto_pdf.name, archivo, "application/pdf")},
                headers={clave: valor for clave, valor in configuracion.get("encabezados", {}).items() if clave.lower() != "content-type"},
                timeout=20,
            )
        return respuesta
    return requests.request(
        metodo,
        configuracion["url"],
        json=cuerpo,
        headers=configuracion.get("encabezados", {}),
        timeout=10,
    )


def enviar_webhook(configuracion: dict, mensaje: str, adjunto_pdf: Path | None = None, embed: dict | None = None) -> None:

    metodo = configuracion.get("metodo", "POST").upper()

    cuerpo = construir_cuerpo_webhook(
        configuracion,
        mensaje,
        embed
    )

    respuesta = solicitar_webhook(metodo, configuracion, cuerpo, adjunto_pdf)

    if embed and respuesta.status_code == 400 and es_webhook_discord(configuracion["url"]):
        respuesta = solicitar_webhook(metodo, configuracion, construir_cuerpo_webhook(configuracion, mensaje), adjunto_pdf)

    if respuesta.status_code >= 400:
        raise RuntimeError(
            f"Webhook respondio HTTP {respuesta.status_code}"
        )


# ==========================================================
# ENVIO POR CORREO ELECTRONICO
# ==========================================================

def enviar_correo(
    configuracion: dict,
    mensaje_alerta: str
) -> None:

    mensaje = EmailMessage()

    mensaje["Subject"] = (
        configuracion.get("asunto")
        or "Alerta de calidad web"
    )

    mensaje["From"] = (
        configuracion.get("remitente")
        or current_app.config["REMITENTE_SMTP"]
    )

    mensaje["To"] = ", ".join(
        configuracion.get("destinatarios", [])
    )

    mensaje.set_content(mensaje_alerta)

    with smtplib.SMTP(
        configuracion.get("servidor")
        or current_app.config["SERVIDOR_SMTP"],
        configuracion.get("puerto")
        or current_app.config["PUERTO_SMTP"],
        timeout=10
    ) as smtp:

        if configuracion.get("tls"):
            smtp.starttls()

        if (
            configuracion.get("usuario")
            and configuracion.get("contrasena")
        ):
            smtp.login(
                configuracion["usuario"],
                configuracion["contrasena"]
            )

        smtp.send_message(mensaje)


# ==========================================================
# REINTENTOS Y NOTIFICACIONES AUTOMATICAS
# ==========================================================

def enviar_canal_con_reintentos(
    canal: CanalNotificacion,
    configuracion: dict,
    mensaje: str,
    adjunto_pdf: Path | None = None,
    embed: dict | None = None,
) -> tuple[str, int, str]:

    ultimo_error = ""

    for intento in range(1, 4):
        try:
            if canal.tipo == "webhook":
                enviar_webhook(configuracion, mensaje, adjunto_pdf, embed)

            elif canal.tipo == "correo":
                enviar_correo(configuracion, mensaje)

            else:
                raise CanalNotificacionInvalido(
                    "Tipo de canal no permitido."
                )

            return "enviada", intento, ""

        except Exception as exc:
            ultimo_error = sanitizar_texto(str(exc))

            if intento < 3:
                time.sleep(intento)

    return "fallida", 3, ultimo_error


def enviar_notificaciones_fallo(ejecucion: Ejecucion) -> None:

    canales = (
        CanalNotificacion.query.filter_by(
            proyecto_id=ejecucion.pipeline.proyecto_id,
            activo=True
        ).all()
        if ejecucion.pipeline
        else []
    )

    if not canales:
        registrar_notificacion(
            ejecucion,
            None,
            "omitida",
            "No hay canales activos configurados"
        )
        return

    try:
        mensaje = crear_mensaje_alerta(ejecucion)
    except Exception:
        current_app.logger.exception("No se pudo construir el resumen de la ejecucion %s", ejecucion.id)
        mensaje = crear_mensaje_alerta_basico(ejecucion)
    adjunto_pdf = None
    if current_app.config.get("ADJUNTAR_PDF_DISCORD", True):
        try:
            from aplicacion.informes.servicio import obtener_o_generar_informe

            informe = obtener_o_generar_informe(ejecucion.id)
            ruta = Path(current_app.config["RUTA_INFORMES"]) / informe.ruta_relativa
            if ruta.exists() and ruta.stat().st_size <= current_app.config.get("TAMANO_MAXIMO_PDF_DISCORD", 8_000_000):
                adjunto_pdf = ruta
        except Exception:
            current_app.logger.exception("No se pudo generar el PDF de la ejecucion %s", ejecucion.id)
            adjunto_pdf = None

    for canal in canales:
        try:
            configuracion = descifrar_configuracion_canal(canal)
        except Exception as exc:
            registrar_notificacion(ejecucion, canal, "fallida", str(exc), 0)
            continue
        es_discord = canal.tipo == "webhook" and es_webhook_discord(configuracion.get("url", ""))
        adjunto_canal = adjunto_pdf if es_discord else None
        embed = crear_embed_discord_seguro(ejecucion, adjunto_canal is not None) if es_discord else None

        estado, intentos, error = enviar_canal_con_reintentos(
            canal,
            configuracion,
            mensaje,
            adjunto_canal,
            embed,
        )

        registrar_notificacion(
            ejecucion,
            canal,
            estado,
            error,
            intentos
        )


# ==========================================================
# ENVIO DE PRUEBA DESDE EL PORTAL QA
# ==========================================================

def probar_canal_notificacion(canal: CanalNotificacion) -> dict:

    configuracion = descifrar_configuracion_canal(canal)

    validar_configuracion_canal(
        canal.tipo,
        configuracion
    )

    mensaje_prueba = (
        "Prueba de notificacion del Sistema Integral de Calidad Web"
    )

    # Webhook: Discord u otro proveedor
    if canal.tipo == "webhook":

        metodo = configuracion.get(
            "metodo",
            "POST"
        ).upper()

        cuerpo = construir_cuerpo_webhook(
            configuracion,
            mensaje_prueba
        )

        respuesta = requests.request(
            metodo,
            configuracion["url"],
            json=cuerpo,
            headers=configuracion.get("encabezados", {}),
            timeout=10,
        )

        return {
            "estado": (
                "enviada"
                if respuesta.status_code < 400
                else "fallida"
            ),
            "codigo_estado": respuesta.status_code
        }

    # Correo electrónico
    mensaje = EmailMessage()

    mensaje["Subject"] = "Prueba de notificacion"

    mensaje["From"] = (
        configuracion.get("remitente")
        or current_app.config["REMITENTE_SMTP"]
    )

    mensaje["To"] = ", ".join(
        configuracion.get("destinatarios", [])
    )

    mensaje.set_content(mensaje_prueba)

    with smtplib.SMTP(
        configuracion.get("servidor")
        or current_app.config["SERVIDOR_SMTP"],
        configuracion.get("puerto")
        or current_app.config["PUERTO_SMTP"],
        timeout=10
    ) as smtp:

        if configuracion.get("tls"):
            smtp.starttls()

        if (
            configuracion.get("usuario")
            and configuracion.get("contrasena")
        ):
            smtp.login(
                configuracion["usuario"],
                configuracion["contrasena"]
            )

        smtp.send_message(mensaje)

    return {
        "estado": "enviada"
    }
