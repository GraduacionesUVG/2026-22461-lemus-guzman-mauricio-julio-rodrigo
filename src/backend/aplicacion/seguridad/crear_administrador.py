import sys

from werkzeug.security import generate_password_hash

from aplicacion import crear_aplicacion
from aplicacion.extensiones import db
from aplicacion.modelos import Rol, Usuario


def crear_administrador(correo: str, nombre: str, contrasena: str) -> None:
    app = crear_aplicacion()
    with app.app_context():
        rol = Rol.query.filter_by(nombre="administrador").first()
        if rol is None:
            rol = Rol(nombre="administrador", descripcion="Gestion completa de la plataforma")
            db.session.add(rol)
        usuario = Usuario.query.filter_by(correo=correo.lower()).first()
        if usuario is None:
            usuario = Usuario(nombre=nombre, correo=correo.lower(), contrasena_hash=generate_password_hash(contrasena), roles=[rol])
            db.session.add(usuario)
        else:
            usuario.nombre = nombre
            usuario.contrasena_hash = generate_password_hash(contrasena)
            usuario.activo = True
            if rol not in usuario.roles:
                usuario.roles.append(rol)
        db.session.commit()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Uso: python -m aplicacion.seguridad.crear_administrador correo nombre contrasena")
    crear_administrador(sys.argv[1], sys.argv[2], sys.argv[3])
