import os

os.environ["ENTORNO_APLICACION"] = "pruebas"
os.environ["CADENA_CONEXION_POSTGRESQL"] = "sqlite://"
os.environ["CLAVE_SESION"] = "pruebas"
os.environ["CLAVE_JWT"] = "pruebas"
os.environ["CLAVE_CIFRADO_SECRETOS"] = "clave-pruebas-segura"

import pytest
from werkzeug.security import generate_password_hash

from aplicacion import crear_aplicacion, crear_roles_iniciales
from aplicacion.extensiones import db
from aplicacion.modelos import Rol, Usuario


@pytest.fixture()
def app():
    aplicacion = crear_aplicacion()
    with aplicacion.app_context():
        db.create_all()
        crear_roles_iniciales()
        rol = Rol.query.filter_by(nombre="administrador").first()
        usuario = Usuario(
            nombre="Administrador",
            correo="usuario@example.invalid",
            contrasena_hash=generate_password_hash("Contrasena123"),
            roles=[rol],
        )
        db.session.add(usuario)
        db.session.commit()
        yield aplicacion
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def cliente(app):
    return app.test_client()


@pytest.fixture()
def cliente_autenticado(cliente):
    cliente.post("/api/autenticacion/iniciar-sesion", json={"correo": "usuario@example.invalid", "contrasena": "Contrasena123"})
    return cliente
