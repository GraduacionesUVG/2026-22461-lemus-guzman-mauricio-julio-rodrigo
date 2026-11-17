from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


SQLITE_LOCAL = Path(os.getenv("QA_SQLITE_LOCAL_PATH", str(PROJECT_ROOT / "almacenamiento" / "calidad_web_dev.db")))
MODO_CONEXION = "configuracion"


def uri_sqlite_local() -> str:
    return f"sqlite:///{SQLITE_LOCAL.as_posix()}"


def preconfigurar_conexion_desde_argv() -> None:
    global MODO_CONEXION
    if "--use-sqlite" in set(sys.argv[1:]):
        os.environ["CADENA_CONEXION_POSTGRESQL"] = uri_sqlite_local()
        os.environ.setdefault("ENTORNO_APLICACION", "desarrollo")
        MODO_CONEXION = "sqlite-local"


preconfigurar_conexion_desde_argv()

from aplicacion import crear_aplicacion  # noqa: E402
from aplicacion.extensiones import db  # noqa: E402
from aplicacion.modelos import (  # noqa: E402
    Alerta,
    Auditoria,
    CanalNotificacion,
    CasoPrueba,
    Entorno,
    Evidencia,
    Ejecucion,
    MedicionEvaluacion,
    ModuloObjetivo,
    Monitor,
    Notificacion,
    PasoCasoPrueba,
    PasoPipeline,
    Pipeline,
    Programacion,
    Proyecto,
    ResultadoPaso,
    RevisionEjecucion,
    RevisionPaso,
    Rol,
    Secreto,
    Usuario,
)
from aplicacion.modelos.entidades import UsuarioRol  # noqa: E402


TABLAS_CONSERVADAS = ["usuarios", "roles", "usuarios_roles", "alembic_version"]
TABLAS_API_LIMPIAS = {
    "proyectos": "/api/proyectos",
    "casos_prueba": "/api/casos-prueba",
    "monitores": "/api/monitores",
    "pipelines": "/api/pipelines",
    "ejecuciones": "/api/ejecuciones",
    "alertas": "/api/alertas",
    "programaciones": "/api/programaciones",
}

MODELOS_OPERATIVOS = [
    Notificacion,
    Alerta,
    RevisionPaso,
    RevisionEjecucion,
    Evidencia,
    ResultadoPaso,
    Ejecucion,
    Programacion,
    PasoPipeline,
    Pipeline,
    PasoCasoPrueba,
    CasoPrueba,
    Monitor,
    CanalNotificacion,
    Secreto,
    Entorno,
    ModuloObjetivo,
    MedicionEvaluacion,
    Auditoria,
    Proyecto,
]

MODELOS_CONSERVADOS = [Usuario, Rol, UsuarioRol]

MENSAJE_CONFIRMACION = "BORRAR DATOS QA"


class LimpiezaCancelada(RuntimeError):
    pass


def sanitizar_uri(uri: str | None) -> str:
    if not uri:
        return "(sin configurar)"
    try:
        url = make_url(uri)
        if url.password:
            url = url.set(password="***")
        return str(url)
    except Exception:
        return "(uri invalida o no imprimible)"


def leer_env_valor(nombre: str) -> str | None:
    ruta = PROJECT_ROOT / ".env"
    if not ruta.exists():
        return None
    for linea in ruta.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not linea or linea.lstrip().startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        if clave.strip() == nombre:
            return valor.strip().strip('"').strip("'")
    return None


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")


def nombre_tabla(modelo) -> str:
    return modelo.__tablename__


def conteos() -> dict[str, int]:
    datos = {}
    for modelo in [*MODELOS_CONSERVADOS, *MODELOS_OPERATIVOS]:
        datos[nombre_tabla(modelo)] = db.session.query(modelo).count()
    return datos


def imprimir_conteos(datos: dict[str, int]) -> None:
    imprimir_diagnostico_conexion()
    print("")
    print("Datos que se conservaran:")
    for tabla in TABLAS_CONSERVADAS:
        if tabla in datos:
            print(f"  {tabla}: {datos[tabla]}")
    print("")
    print("Datos operativos que se eliminaran:")
    for modelo in MODELOS_OPERATIVOS:
        tabla = nombre_tabla(modelo)
        print(f"  {tabla}: {datos.get(tabla, 0)}")


def validar_entorno_seguro(app) -> None:
    entorno = app.config.get("ENTORNO_APLICACION", "")
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if entorno.lower() in {"produccion", "production", "prod"}:
        raise LimpiezaCancelada("Entorno de produccion detectado. Limpieza cancelada.")
    if not uri:
        raise LimpiezaCancelada("No existe SQLALCHEMY_DATABASE_URI configurado.")

    url = make_url(uri)
    if url.drivername.startswith("sqlite"):
        db_path = str(url.database or "")
        if db_path and db_path != ":memory:":
            resolved = Path(db_path).resolve()
            if entorno != "pruebas" and PROJECT_ROOT not in resolved.parents and resolved != PROJECT_ROOT:
                raise LimpiezaCancelada(f"SQLite fuera del proyecto QA: {resolved}")
            if entorno != "pruebas" and resolved.name != "calidad_web_dev.db":
                raise LimpiezaCancelada(f"SQLite local no reconocida como base QA: {resolved}")
        return

    if url.drivername.startswith("postgresql"):
        host = (url.host or "").lower()
        database = (url.database or "").lower()
        if host not in {"localhost", "127.0.0.1", "::1"}:
            raise LimpiezaCancelada(f"Base PostgreSQL no local detectada: host={host}")
        if not any(token in database for token in ["calidad", "qa", "test", "prueba"]):
            raise LimpiezaCancelada(f"Nombre de base no reconocido como QA: {database}")
        inspector = inspect(db.engine)
        requeridas = {"usuarios", "roles", "proyectos", "ejecuciones", "evidencias"}
        existentes = set(inspector.get_table_names())
        faltantes = sorted(requeridas - existentes)
        if faltantes:
            raise LimpiezaCancelada(f"La base no parece ser del Sistema QA. Faltan tablas: {', '.join(faltantes)}")
        return

    raise LimpiezaCancelada(f"Motor no autorizado para limpieza: {url.drivername}")


def procesos_activos_desde_pidfiles() -> list[str]:
    activos = []
    log_dir = PROJECT_ROOT / ".logs"
    for nombre in ["trabajador.pid", "programador.pid"]:
        ruta = log_dir / nombre
        if not ruta.exists():
            continue
        pid = ruta.read_text(encoding="utf-8", errors="ignore").strip()
        if not pid.isdigit():
            continue
        if proceso_existe(int(pid)):
            activos.append(f"{nombre}: PID {pid}")
    return activos


def proceso_existe(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        resultado = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        salida = resultado.stdout.lower()
        return str(pid) in salida and "no tasks" not in salida and "ninguna tarea" not in salida
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def ejecuciones_activas() -> int:
    return db.session.query(Ejecucion).filter(Ejecucion.estado.in_(["en_cola", "en_ejecucion"])).count()


def validar_sin_procesos_activos() -> None:
    activos = procesos_activos_desde_pidfiles()
    en_curso = ejecuciones_activas()
    if en_curso:
        activos.append(f"ejecuciones en cola/en ejecucion: {en_curso}")
    if activos:
        detalle = "\n  - ".join(activos)
        raise LimpiezaCancelada(
            "Hay workers, programadores o ejecuciones activas. Detenlos antes de limpiar:\n  - "
            + detalle
        )


def detener_servicios_locales() -> None:
    if os.name != "nt":
        raise LimpiezaCancelada("La detencion automatica solo esta disponible en Windows.")
    resultado = subprocess.run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        str(PROJECT_ROOT / "scripts" / "detener_servicios_qa.ps1"),
    ])
    if resultado.returncode != 0:
        raise LimpiezaCancelada("No se pudieron detener los servicios QA. No se elimino ningun dato.")
    activos = procesos_activos_desde_pidfiles()
    if activos:
        raise LimpiezaCancelada("Siguen activos servicios QA: " + ", ".join(activos))


def ruta_respaldos() -> Path:
    ruta = PROJECT_ROOT / "almacenamiento" / "respaldos_limpieza"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def respaldo_logico(destino: Path) -> Path:
    inspector = inspect(db.engine)
    salida = {
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "motor": str(db.engine.url).replace(str(db.engine.url.password or ""), "***") if db.engine.url.password else str(db.engine.url),
        "tablas": {},
    }
    with db.engine.connect() as conn:
        for tabla in inspector.get_table_names():
            filas = conn.execute(text(f"SELECT * FROM {tabla}")).mappings().all()
            salida["tablas"][tabla] = [dict(fila) for fila in filas]
    destino.write_text(json.dumps(salida, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
    return destino


def imprimir_diagnostico_conexion() -> None:
    print("")
    print("Diagnostico seguro de conexion:")
    print(f"  .env CADENA_CONEXION_POSTGRESQL: {sanitizar_uri(leer_env_valor('CADENA_CONEXION_POSTGRESQL'))}")
    print(f"  SQLite usada por INICIAR_SISTEMA_QA.bat -UseSqlite: {sanitizar_uri(uri_sqlite_local())}")
    print(f"  SQLite existe: {'si' if SQLITE_LOCAL.exists() else 'no'} ({SQLITE_LOCAL})")
    print(f"  Limpiador modo: {MODO_CONEXION}")
    print(f"  Limpiador conexion efectiva: {sanitizar_uri(str(db.engine.url))}")


def crear_respaldo() -> Path:
    destino_dir = ruta_respaldos()
    uri = db.engine.url
    stamp = utc_stamp()
    if uri.drivername.startswith("sqlite") and uri.database and uri.database != ":memory:":
        origen = Path(uri.database).resolve()
        destino = destino_dir / f"respaldo_qa_{stamp}.sqlite"
        # Incluye los cambios del WAL y produce una imagen consistente de SQLite.
        with sqlite3.connect(str(origen)) as fuente, sqlite3.connect(str(destino)) as copia:
            fuente.backup(copia)
        if not destino.exists() or destino.stat().st_size == 0:
            raise LimpiezaCancelada("El respaldo SQLite no se genero correctamente.")
        return destino

    if uri.drivername.startswith("postgresql"):
        pg_dump = shutil.which("pg_dump")
        if pg_dump:
            destino = destino_dir / f"respaldo_qa_{stamp}.dump"
            comando = [pg_dump, "--format=custom", "--file", str(destino), str(uri)]
            resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if resultado.returncode == 0 and destino.exists() and destino.stat().st_size > 0:
                return destino
        destino = destino_dir / f"respaldo_qa_{stamp}.json"
        respaldo_logico(destino)
        if not destino.exists() or destino.stat().st_size == 0:
            raise LimpiezaCancelada("El respaldo logico no se genero correctamente.")
        return destino

    destino = destino_dir / f"respaldo_qa_{stamp}.json"
    respaldo_logico(destino)
    if not destino.exists() or destino.stat().st_size == 0:
        raise LimpiezaCancelada("El respaldo logico no se genero correctamente.")
    return destino


def resolver_ruta_evidencias(app) -> Path:
    configurada = Path(app.config.get("RUTA_EVIDENCIAS", "almacenamiento/evidencias"))
    if not configurada.is_absolute():
        configurada = PROJECT_ROOT / configurada
    return configurada.resolve()


def validar_ruta_evidencias(ruta: Path) -> None:
    raiz_autorizada = (PROJECT_ROOT / "almacenamiento" / "evidencias").resolve()
    if ruta != raiz_autorizada and raiz_autorizada not in ruta.parents:
        raise LimpiezaCancelada(f"Ruta de evidencias no autorizada: {ruta}")


def limpiar_archivos_evidencia(app) -> int:
    ruta = resolver_ruta_evidencias(app)
    validar_ruta_evidencias(ruta)
    if not ruta.exists():
        ruta.mkdir(parents=True, exist_ok=True)
        return 0
    eliminados = 0
    for item in ruta.iterdir():
        if item.name == ".gitkeep":
            continue
        if item.is_dir():
            shutil.rmtree(item)
            eliminados += 1
        elif item.is_file():
            item.unlink()
            eliminados += 1
    return eliminados


def limpiar_base_transaccional() -> dict[str, int]:
    eliminados = {}
    try:
        for modelo in MODELOS_OPERATIVOS:
            cantidad = db.session.query(modelo).delete(synchronize_session=False)
            eliminados[nombre_tabla(modelo)] = cantidad
        db.session.commit()
        return eliminados
    except Exception:
        db.session.rollback()
        raise


def verificar_limpieza() -> tuple[bool, list[str]]:
    errores = []
    if db.session.query(Usuario).count() == 0:
        errores.append("No quedan usuarios.")
    if db.session.query(Rol).count() == 0:
        errores.append("No quedan roles.")
    for modelo in MODELOS_OPERATIVOS:
        cantidad = db.session.query(modelo).count()
        if cantidad:
            errores.append(f"{nombre_tabla(modelo)} conserva {cantidad} registros.")
    return not errores, errores


def obtener_conteos_api() -> dict[str, int]:
    base_url = os.getenv("QA_BACKEND_URL", os.getenv("URL_PUBLICA_BACKEND", "http://127.0.0.1:5000")).rstrip("/") + "/"
    correo = os.getenv("QA_ADMIN_EMAIL", "usuario@example.invalid")
    contrasena = os.getenv("QA_ADMIN_PASSWORD", "REEMPLAZAR_SECRETO_LOCAL")
    sesion = requests.Session()
    respuesta = sesion.post(
        urljoin(base_url, "api/autenticacion/iniciar-sesion"),
        json={"correo": correo, "contrasena": contrasena},
        timeout=5,
    )
    if respuesta.status_code >= 400:
        raise LimpiezaCancelada(
            f"No se pudo autenticar contra la API real en {base_url.rstrip('/')}. Estado HTTP {respuesta.status_code}."
        )

    conteos_api: dict[str, int] = {}
    respuesta_resumen = sesion.get(urljoin(base_url, "api/metricas/resumen"), timeout=5)
    if respuesta_resumen.status_code >= 400:
        raise LimpiezaCancelada(f"La API real no devolvio metricas/resumen. Estado HTTP {respuesta_resumen.status_code}.")
    conteos_api["resumen.ejecuciones"] = int((respuesta_resumen.json() or {}).get("ejecuciones", 0))

    for nombre, ruta in TABLAS_API_LIMPIAS.items():
        respuesta_lista = sesion.get(urljoin(base_url, ruta.lstrip("/")), timeout=5)
        if respuesta_lista.status_code >= 400:
            conteos_api[f"api.{nombre}"] = -1
            continue
        datos = respuesta_lista.json() or {}
        elementos = datos.get("elementos", [])
        conteos_api[f"api.{nombre}"] = len(elementos) if isinstance(elementos, list) else 0
    return conteos_api


def imprimir_conteos_api(conteos_api: dict[str, int]) -> None:
    print("")
    print("Conteos devueltos por la API real:")
    for nombre, cantidad in conteos_api.items():
        valor = "sin permiso o no disponible" if cantidad < 0 else str(cantidad)
        print(f"  {nombre}: {valor}")


def verificar_api_limpia() -> None:
    try:
        conteos_api = obtener_conteos_api()
    except requests.RequestException as exc:
        print(f"Aviso: API no disponible; verificacion directa de la base completada. Detalle: {exc}")
        return
    imprimir_conteos_api(conteos_api)
    pendientes = [f"{nombre}={cantidad}" for nombre, cantidad in conteos_api.items() if cantidad > 0]
    if pendientes:
        raise LimpiezaCancelada(
            "La base directa quedo limpia, pero la API real aun devuelve datos antiguos: "
            + ", ".join(pendientes)
        )


def pedir_confirmacion() -> None:
    print("")
    print("ESTA OPERACION ELIMINARA TODOS LOS PROYECTOS, PRUEBAS, PIPELINES, EJECUCIONES, MONITORES, ALERTAS Y EVIDENCIAS DEL SISTEMA QA. LOS USUARIOS SE CONSERVARAN.")
    escrito = input(f"Escribe exactamente '{MENSAJE_CONFIRMACION}' para continuar: ").strip()
    if escrito != MENSAJE_CONFIRMACION:
        raise LimpiezaCancelada("Confirmacion incorrecta. No se elimino nada.")


def comando_simular(app) -> None:
    validar_entorno_seguro(app)
    imprimir_conteos(conteos())
    print("")
    print("Simulacion completada. No se elimino ningun dato.")


def comando_limpiar(app, confirmar: bool = True, verificar_api: bool = False, detener_servicios: bool = False) -> None:
    validar_entorno_seguro(app)
    validar_ruta_evidencias(resolver_ruta_evidencias(app))
    if not detener_servicios:
        validar_sin_procesos_activos()
    imprimir_conteos(conteos())
    if detener_servicios:
        print("Se detendran backend, trabajador y programador de este proyecto antes de limpiar.")
        print("Las ejecuciones pendientes tambien se eliminaran. Al terminar, ejecuta INICIAR_SISTEMA_QA.bat.")
    if confirmar:
        pedir_confirmacion()
    if detener_servicios:
        # Cierra la transaccion de lectura antes de detener los escritores y respaldar.
        db.session.remove()
        detener_servicios_locales()
    respaldo = crear_respaldo()
    print("")
    print(f"Respaldo creado: {respaldo}")
    eliminados = limpiar_base_transaccional()
    archivos = limpiar_archivos_evidencia(app)
    ok, errores = verificar_limpieza()
    print("")
    print("Resumen de limpieza:")
    for tabla, cantidad in eliminados.items():
        print(f"  {tabla}: {cantidad}")
    print(f"  entradas/archivos de evidencia eliminados: {archivos}")
    if not ok:
        raise LimpiezaCancelada("La verificacion posterior encontro problemas: " + "; ".join(errores))
    if verificar_api:
        verificar_api_limpia()
    print("Limpieza completada. Usuarios y roles conservados.")


def comando_verificar(app, verificar_api: bool = False) -> None:
    validar_entorno_seguro(app)
    ok, errores = verificar_limpieza()
    print("")
    print("Estado del sistema QA:")
    print(f"  usuarios: {db.session.query(Usuario).count()}")
    print(f"  roles: {db.session.query(Rol).count()}")
    for modelo in MODELOS_OPERATIVOS:
        print(f"  {nombre_tabla(modelo)}: {db.session.query(modelo).count()}")
    if errores:
        print("")
        print("Pendientes:")
        for error in errores:
            print(f"  - {error}")
        raise SystemExit(1)
    if verificar_api:
        verificar_api_limpia()
    print("")
    print("Verificacion correcta: sistema sin datos operativos y autenticacion preservada.")


def crear_app():
    os.chdir(PROJECT_ROOT)
    return crear_aplicacion()


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Limpiador seguro del Sistema Integral de Calidad Web")
    parser.add_argument("accion", choices=["simular", "limpiar", "verificar"])
    parser.add_argument("--use-sqlite", action="store_true", help="Usa la SQLite local que usa INICIAR_SISTEMA_QA.bat -UseSqlite.")
    parser.add_argument("--sin-confirmacion", action="store_true", help="Solo para pruebas automatizadas.")
    parser.add_argument("--sin-api", action="store_true", help="Solo para pruebas automatizadas con base temporal.")
    parser.add_argument("--verificar-api", action="store_true", help="Consulta adicionalmente la API si esta encendida.")
    parser.add_argument("--detener-servicios", action="store_true", help="Detiene los servicios Windows de este proyecto y elimina tambien ejecuciones pendientes.")
    args = parser.parse_args(argv)

    app = crear_app()
    with app.app_context():
        try:
            if args.accion == "simular":
                comando_simular(app)
            elif args.accion == "limpiar":
                comando_limpiar(app, confirmar=not args.sin_confirmacion, verificar_api=args.verificar_api and not args.sin_api, detener_servicios=args.detener_servicios)
            else:
                comando_verificar(app, verificar_api=args.verificar_api and not args.sin_api)
        except LimpiezaCancelada as exc:
            print("")
            print(f"OPERACION CANCELADA: {exc}")
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
