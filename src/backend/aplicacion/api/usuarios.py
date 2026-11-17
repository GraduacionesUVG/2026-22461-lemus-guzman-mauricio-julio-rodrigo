from uuid import UUID

from flask import Blueprint, request
from werkzeug.security import generate_password_hash

from aplicacion.extensiones import db
from aplicacion.modelos import Rol, Usuario
from aplicacion.seguridad.permisos import requiere_roles
from aplicacion.servicios.serializacion import serializar_usuario
from aplicacion.utilidades.respuestas import respuesta_error, respuesta_exitosa


bp = Blueprint("usuarios", __name__, url_prefix="/api/usuarios")
ROLES_GESTIONABLES = {"administrador", "qa", "devops", "responsable"}


def validar_datos_usuario(datos: dict, requiere_contrasena: bool = True):
    if not datos.get("nombre", "").strip():
        return respuesta_error("nombre_requerido", "El nombre del usuario es obligatorio.", 400)
    if not datos.get("correo", "").strip():
        return respuesta_error("correo_requerido", "El correo del usuario es obligatorio.", 400)
    if requiere_contrasena and not datos.get("contrasena", "").strip():
        return respuesta_error("contrasena_requerida", "La contrasena temporal es obligatoria.", 400)
    roles = set(datos.get("roles", []))
    if not roles:
        return respuesta_error("rol_requerido", "Seleccione al menos un rol.", 400)
    if not roles.issubset(ROLES_GESTIONABLES):
        return respuesta_error("rol_invalido", "Uno de los roles indicados no existe.", 400)
    return None


@bp.get("")
@requiere_roles("administrador")
def listar_usuarios():
    usuarios = Usuario.query.order_by(Usuario.creado_en.desc()).all()
    return respuesta_exitosa({"elementos": [serializar_usuario(usuario) for usuario in usuarios]})


@bp.get("/roles")
@requiere_roles("administrador")
def listar_roles():
    roles = Rol.query.filter(Rol.nombre.in_(ROLES_GESTIONABLES)).order_by(Rol.nombre.asc()).all()
    return respuesta_exitosa({"elementos": [{"id": str(rol.id), "nombre": rol.nombre, "descripcion": rol.descripcion} for rol in roles]})


@bp.post("")
@requiere_roles("administrador")
def crear_usuario():
    datos = request.get_json() or {}
    error = validar_datos_usuario(datos)
    if error:
        return error
    if Usuario.query.filter_by(correo=datos["correo"].lower()).first():
        return respuesta_error("usuario_existente", "Ya existe un usuario con ese correo.", 409)
    roles = Rol.query.filter(Rol.nombre.in_(datos["roles"])).all()
    usuario = Usuario(
        nombre=datos["nombre"].strip(),
        correo=datos["correo"].lower(),
        contrasena_hash=generate_password_hash(datos["contrasena"]),
        activo=datos.get("activo", True),
        roles=roles,
    )
    db.session.add(usuario)
    db.session.commit()
    return respuesta_exitosa(serializar_usuario(usuario), 201)


@bp.get("/<uuid:usuario_id>")
@requiere_roles("administrador")
def obtener_usuario(usuario_id: UUID):
    return respuesta_exitosa(serializar_usuario(Usuario.query.get_or_404(usuario_id)))


@bp.patch("/<uuid:usuario_id>")
@requiere_roles("administrador")
def actualizar_usuario(usuario_id: UUID):
    usuario = Usuario.query.get_or_404(usuario_id)
    datos = request.get_json() or {}
    if "nombre" in datos:
        if not datos["nombre"].strip():
            return respuesta_error("nombre_requerido", "El nombre del usuario es obligatorio.", 400)
        usuario.nombre = datos["nombre"].strip()
    if "activo" in datos:
        usuario.activo = datos["activo"]
    if "roles" in datos:
        roles = set(datos["roles"])
        if not roles or not roles.issubset(ROLES_GESTIONABLES):
            return respuesta_error("rol_invalido", "Seleccione roles validos.", 400)
        usuario.roles = Rol.query.filter(Rol.nombre.in_(roles)).all()
    db.session.commit()
    return respuesta_exitosa(serializar_usuario(usuario))


@bp.post("/<uuid:usuario_id>/restablecer-contrasena")
@requiere_roles("administrador")
def restablecer_contrasena(usuario_id: UUID):
    usuario = Usuario.query.get_or_404(usuario_id)
    datos = request.get_json() or {}
    if not datos.get("contrasena", "").strip():
        return respuesta_error("contrasena_requerida", "La nueva contrasena es obligatoria.", 400)
    usuario.contrasena_hash = generate_password_hash(datos["contrasena"])
    db.session.commit()
    return respuesta_exitosa({"mensaje": "Contrasena actualizada"})
