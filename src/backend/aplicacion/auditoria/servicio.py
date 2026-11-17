from flask import request
from flask_jwt_extended import get_jwt_identity
from uuid import UUID

from aplicacion.extensiones import db
from aplicacion.modelos import Auditoria
from aplicacion.utilidades.sanitizacion import sanitizar_diccionario


def registrar_auditoria(accion: str, entidad: str, entidad_id: str | None = None, datos: dict | None = None) -> None:
    usuario_id = None
    try:
        identidad = get_jwt_identity()
        usuario_id = UUID(identidad) if identidad else None
    except Exception:
        usuario_id = None
    auditoria = Auditoria(
        usuario_id=usuario_id,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        datos_sanitizados=sanitizar_diccionario(datos),
        direccion_ip=request.remote_addr if request else None,
    )
    db.session.add(auditoria)
