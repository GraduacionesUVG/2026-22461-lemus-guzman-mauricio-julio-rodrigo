from flask import Flask
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from aplicacion.api.autenticacion import bp as autenticacion_bp
from aplicacion.api.demo_objetivo import bp as demo_objetivo_bp
from aplicacion.api.metricas_yaml import bp as metricas_yaml_bp
from aplicacion.api.rutas import bp as api_bp
from aplicacion.api.usuarios import bp as usuarios_bp
from aplicacion.configuracion.ajustes import obtener_configuracion, validar_configuracion
from aplicacion.extensiones import db, jwt, migrate
from aplicacion.modelos import Rol
from aplicacion.servicios.validaciones import ConfiguracionInvalida
from aplicacion.utilidades.respuestas import respuesta_error


def crear_roles_iniciales() -> None:
    roles = {
        "administrador": "Gestion completa de la plataforma",
        "qa": "Gestion de pruebas funcionales y ejecuciones",
        "devops": "Gestion de entornos, monitores y programaciones",
        "responsable": "Consulta dashboard, historial, reportes y alertas",
    }
    for nombre, descripcion in roles.items():
        if Rol.query.filter_by(nombre=nombre).first() is None:
            db.session.add(Rol(nombre=nombre, descripcion=descripcion))
    db.session.commit()


def crear_aplicacion(configuracion=None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(configuracion or obtener_configuracion())
    validar_configuracion(app)
    CORS(app, origins=[app.config["ORIGEN_FRONTEND_PERMITIDO"]], supports_credentials=True)
    db.init_app(app)
    migrate.init_app(app, db, directory="migraciones")
    jwt.init_app(app)
    app.register_blueprint(autenticacion_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(metricas_yaml_bp)
    app.register_blueprint(demo_objetivo_bp)

    @app.get("/api/salud")
    def salud():
        return {"estado": "disponible"}

    @app.errorhandler(ConfiguracionInvalida)
    def manejar_configuracion_invalida(error):
        return respuesta_error("configuracion_invalida", str(error), 400)

    @app.errorhandler(HTTPException)
    def manejar_http(error):
        return respuesta_error("solicitud_invalida", error.description, error.code)

    @app.errorhandler(Exception)
    def manejar_error(error):
        if app.config.get("TESTING"):
            raise error
        return respuesta_error("error_interno", "La plataforma no pudo completar la solicitud.", 500)

    with app.app_context():
        try:
            crear_roles_iniciales()
        except Exception:
            db.session.rollback()
    return app
