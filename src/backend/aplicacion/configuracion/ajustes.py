import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[3] / ".env")


class ConfiguracionBase:
    ENTORNO_APLICACION = os.getenv("ENTORNO_APLICACION", "desarrollo")
    SQLALCHEMY_DATABASE_URI = os.getenv("CADENA_CONEXION_POSTGRESQL", "")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("CLAVE_SESION", "")
    JWT_SECRET_KEY = os.getenv("CLAVE_JWT", "")
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_COOKIE_SECURE = ENTORNO_APLICACION == "produccion"
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    RUTA_EVIDENCIAS = os.getenv("RUTA_EVIDENCIAS", "almacenamiento/evidencias")
    RUTA_INFORMES = os.getenv("RUTA_INFORMES", "almacenamiento/informes")
    ZONA_HORARIA_APLICACION = os.getenv("ZONA_HORARIA_APLICACION", "America/Guatemala")
    ADJUNTAR_PDF_DISCORD = os.getenv("ADJUNTAR_PDF_DISCORD", "true").lower() == "true"
    TAMANO_MAXIMO_PDF_DISCORD = int(os.getenv("TAMANO_MAXIMO_PDF_DISCORD", "8000000"))
    ORIGEN_FRONTEND_PERMITIDO = os.getenv("ORIGEN_FRONTEND_PERMITIDO", "http://localhost:5173")
    CLAVE_CIFRADO_SECRETOS = os.getenv("CLAVE_CIFRADO_SECRETOS", "")
    TIEMPO_ESPERA_PREDETERMINADO = int(os.getenv("TIEMPO_ESPERA_PREDETERMINADO", "15"))
    MODO_HEADLESS = os.getenv("MODO_HEADLESS", "true").lower() == "true"
    NAVEGADOR_SELENIUM = os.getenv("NAVEGADOR_SELENIUM", "chrome")
    SERVIDOR_SMTP = os.getenv("SERVIDOR_SMTP", "localhost")
    PUERTO_SMTP = int(os.getenv("PUERTO_SMTP", "1025"))
    USUARIO_SMTP = os.getenv("USUARIO_SMTP", "")
    CONTRASENA_SMTP = os.getenv("CONTRASENA_SMTP", "")
    REMITENTE_SMTP = os.getenv("REMITENTE_SMTP", "usuario@example.invalid")


class ConfiguracionPruebas(ConfiguracionBase):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv("CADENA_CONEXION_POSTGRESQL", "sqlite://")
    JWT_COOKIE_CSRF_PROTECT = False


def obtener_configuracion() -> type[ConfiguracionBase]:
    if os.getenv("ENTORNO_APLICACION") == "pruebas":
        return ConfiguracionPruebas
    return ConfiguracionBase


def validar_configuracion(app) -> None:
    obligatorias = [
        "SQLALCHEMY_DATABASE_URI",
        "SECRET_KEY",
        "JWT_SECRET_KEY",
        "CLAVE_CIFRADO_SECRETOS",
    ]
    faltantes = [nombre for nombre in obligatorias if not app.config.get(nombre)]
    if faltantes and not app.config.get("TESTING"):
        raise RuntimeError(f"Faltan variables obligatorias: {', '.join(faltantes)}")
