from datetime import datetime, timezone
from uuid import UUID

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, set_access_cookies, unset_jwt_cookies
from werkzeug.security import check_password_hash, generate_password_hash

from aplicacion.extensiones import db
from aplicacion.modelos import Rol, Usuario
from aplicacion.servicios.serializacion import serializar_usuario
from aplicacion.utilidades.respuestas import respuesta_error, respuesta_exitosa


bp = Blueprint("autenticacion", __name__, url_prefix="/api/autenticacion")


@bp.post("/iniciar-sesion")
def iniciar_sesion():
    datos = request.get_json() or {}
    usuario = Usuario.query.filter_by(correo=datos.get("correo", "").lower()).first()
    if usuario is None or not usuario.activo or not check_password_hash(usuario.contrasena_hash, datos.get("contrasena", "")):
        return respuesta_error("credenciales_invalidas", "Correo o contrasena incorrectos.", 401)
    usuario.ultimo_acceso = datetime.now(timezone.utc)
    db.session.commit()
    roles = [rol.nombre for rol in usuario.roles]
    token = create_access_token(identity=str(usuario.id), additional_claims={"roles": roles})
    respuesta = jsonify({"usuario": serializar_usuario(usuario)})
    set_access_cookies(respuesta, token)
    return respuesta


@bp.post("/cerrar-sesion")
def cerrar_sesion():
    respuesta = jsonify({"mensaje": "Sesion cerrada"})
    unset_jwt_cookies(respuesta)
    return respuesta


@bp.post("/renovar-sesion")
@jwt_required()
def renovar_sesion():
    usuario = Usuario.query.get_or_404(UUID(get_jwt_identity()))
    token = create_access_token(identity=str(usuario.id), additional_claims={"roles": [rol.nombre for rol in usuario.roles]})
    respuesta = jsonify({"usuario": serializar_usuario(usuario)})
    set_access_cookies(respuesta, token)
    return respuesta


@bp.get("/sesion-actual")
@jwt_required()
def sesion_actual():
    usuario = Usuario.query.get_or_404(UUID(get_jwt_identity()))
    return respuesta_exitosa({"usuario": serializar_usuario(usuario)})


@bp.patch("/preferencias")
@jwt_required()
def actualizar_preferencias():
    usuario = Usuario.query.get_or_404(UUID(get_jwt_identity()))
    datos = request.get_json() or {}
    if "tour_completado" in datos:
        usuario.tour_completado = bool(datos["tour_completado"])
    db.session.commit()
    return respuesta_exitosa({"usuario": serializar_usuario(usuario)})


@bp.post("/registrar")
def registrar_usuario():
    datos = request.get_json() or {}
    if Usuario.query.filter_by(correo=datos.get("correo", "").lower()).first():
        return respuesta_error("usuario_existente", "Ya existe un usuario con ese correo.", 409)
    rol = Rol.query.filter_by(nombre=datos.get("rol", "responsable")).first()
    if rol is None:
        rol = Rol(nombre="responsable", descripcion="Consulta resultados y alertas autorizadas")
        db.session.add(rol)
    usuario = Usuario(
        nombre=datos["nombre"],
        correo=datos["correo"].lower(),
        contrasena_hash=generate_password_hash(datos["contrasena"]),
        roles=[rol],
    )
    db.session.add(usuario)
    db.session.commit()
    return respuesta_exitosa({"usuario": serializar_usuario(usuario)}, 201)
