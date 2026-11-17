from functools import wraps

from flask_jwt_extended import get_jwt, verify_jwt_in_request

from aplicacion.utilidades.respuestas import respuesta_error


def requiere_roles(*roles_permitidos: str):
    def decorar(funcion):
        @wraps(funcion)
        def envolver(*args, **kwargs):
            verify_jwt_in_request()
            roles = set(get_jwt().get("roles", []))
            if "administrador" in roles or roles.intersection(roles_permitidos):
                return funcion(*args, **kwargs)
            return respuesta_error("permiso_denegado", "No tiene permiso para realizar esta accion.", 403)

        return envolver

    return decorar
