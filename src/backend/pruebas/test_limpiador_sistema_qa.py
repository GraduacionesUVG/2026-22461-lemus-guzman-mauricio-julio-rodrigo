from pathlib import Path
from uuid import UUID

import pytest
from werkzeug.security import check_password_hash

from aplicacion.extensiones import db
from aplicacion.modelos import (
    Alerta,
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

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = PROJECT_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import limpiar_sistema_qa as limpiador


def crear_datos_operativos(app, tmp_path):
    app.config["RUTA_EVIDENCIAS"] = str(tmp_path / "almacenamiento" / "evidencias")
    usuario = Usuario.query.filter_by(correo="usuario@example.invalid").first()
    proyecto = Proyecto(nombre="Proyecto limpieza", descripcion="Demo", creado_por=usuario.id)
    db.session.add(proyecto)
    db.session.flush()
    modulo = ModuloObjetivo(proyecto_id=proyecto.id, nombre="Modulo")
    entorno = Entorno(proyecto_id=proyecto.id, nombre="local", url_base="http://localhost")
    secreto = Secreto(proyecto_id=proyecto.id, nombre="clave", tipo="password", valor_cifrado="cifrado", creado_por=usuario.id)
    caso = CasoPrueba(proyecto_id=proyecto.id, modulo_objetivo_id=modulo.id, nombre="Caso", creado_por=usuario.id)
    paso_caso = PasoCasoPrueba(caso_prueba=caso, orden=1, tipo="navegar", nombre="Abrir", configuracion={"ruta": "/"})
    monitor = Monitor(proyecto_id=proyecto.id, entorno_id=entorno.id, nombre="HTTP", tipo="http", configuracion={"ruta": "/"})
    pipeline = Pipeline(proyecto_id=proyecto.id, nombre="Pipeline", creado_por=usuario.id)
    paso_pipeline = PasoPipeline(pipeline=pipeline, orden=1, tipo="caso_prueba", caso_prueba_id=caso.id, nombre="Caso")
    ejecucion = Ejecucion(pipeline=pipeline, entorno=entorno, origen="manual", estado="exitosa", creado_por=usuario.id)
    resultado = ResultadoPaso(ejecucion=ejecucion, paso_pipeline_id=paso_pipeline.id, paso_caso_prueba_id=paso_caso.id, tipo="caso_prueba", estado="exitosa")
    db.session.add_all([modulo, entorno, secreto, caso, paso_caso, monitor, pipeline, paso_pipeline, ejecucion, resultado])
    db.session.flush()
    programacion = Programacion(pipeline_id=pipeline.id, nombre="Diaria", tipo_frecuencia="diaria", configuracion_frecuencia={"hora": "06:00"})
    db.session.add(programacion)
    revision_ejecucion = RevisionEjecucion(ejecucion_id=ejecucion.id, clasificacion="confirmada", revisado_por=usuario.id)
    revision_paso = RevisionPaso(resultado_paso_id=resultado.id, clasificacion="confirmado", revisado_por=usuario.id)
    evidencia_dir = Path(app.config["RUTA_EVIDENCIAS"]) / str(ejecucion.id)
    evidencia_dir.mkdir(parents=True)
    evidencia_file = evidencia_dir / "captura.png"
    evidencia_file.write_bytes(b"png")
    evidencia = Evidencia(ejecucion_id=ejecucion.id, resultado_paso_id=resultado.id, tipo="captura", nombre_archivo="captura.png", ruta_relativa=f"{ejecucion.id}/captura.png", tipo_contenido="image/png", tamano_bytes=3, hash_sha256="0" * 64)
    alerta = Alerta(ejecucion_id=ejecucion.id, tipo="pipeline", severidad="media")
    notificacion = Notificacion(ejecucion_id=ejecucion.id, estado="omitida")
    medicion = MedicionEvaluacion(proyecto_id=proyecto.id, escenario="CP", enfoque="integrado")
    db.session.add_all([revision_ejecucion, revision_paso, evidencia, alerta, notificacion, medicion])
    db.session.commit()
    return usuario.id, usuario.contrasena_hash, evidencia_file


def test_limpieza_conserva_usuarios_roles_y_hashes(app, tmp_path, monkeypatch):
    usuario_id, hash_original, evidencia = crear_datos_operativos(app, tmp_path)
    monkeypatch.setattr(limpiador, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(limpiador, "crear_respaldo", lambda: tmp_path / "backup.json")

    eliminados = limpiador.limpiar_base_transaccional()
    archivos = limpiador.limpiar_archivos_evidencia(app)

    usuario = Usuario.query.get(usuario_id)
    assert usuario is not None
    assert usuario.contrasena_hash == hash_original
    assert check_password_hash(usuario.contrasena_hash, "Contrasena123")
    assert Rol.query.count() >= 1
    assert all(db.session.query(modelo).count() == 0 for modelo in limpiador.MODELOS_OPERATIVOS)
    assert eliminados["proyectos"] == 1
    assert archivos == 1
    assert not evidencia.exists()


def test_limpieza_es_idempotente(app, tmp_path, monkeypatch):
    crear_datos_operativos(app, tmp_path)
    monkeypatch.setattr(limpiador, "PROJECT_ROOT", tmp_path)
    limpiador.limpiar_base_transaccional()
    limpiador.limpiar_archivos_evidencia(app)
    limpiador.limpiar_base_transaccional()
    limpiador.limpiar_archivos_evidencia(app)
    ok, errores = limpiador.verificar_limpieza()
    assert ok
    assert errores == []


def test_cancelacion_si_respaldo_falla(app, tmp_path, monkeypatch):
    crear_datos_operativos(app, tmp_path)
    monkeypatch.setattr(limpiador, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(limpiador, "validar_sin_procesos_activos", lambda: None)

    def falla():
        raise limpiador.LimpiezaCancelada("backup fallo")

    monkeypatch.setattr(limpiador, "crear_respaldo", falla)
    with pytest.raises(limpiador.LimpiezaCancelada):
        limpiador.comando_limpiar(app, confirmar=False)
    assert Proyecto.query.count() == 1


def test_cancelacion_si_base_no_es_qa(app, monkeypatch):
    app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql+psycopg://usuario:REEMPLAZAR_SECRETO_LOCAL@db.remota.example.com:5432/produccion"
    with pytest.raises(limpiador.LimpiezaCancelada):
        limpiador.validar_entorno_seguro(app)


def test_ruta_evidencias_protege_ecommerce(app):
    with pytest.raises(limpiador.LimpiezaCancelada):
        limpiador.validar_ruta_evidencias((PROJECT_ROOT.parent / "ecommerce").resolve())


def test_respaldo_logico_temporal(app, tmp_path):
    crear_datos_operativos(app, tmp_path)
    destino = tmp_path / "respaldo.json"
    limpiador.respaldo_logico(destino)
    assert destino.exists()
    contenido = destino.read_text(encoding="utf-8")
    assert "usuarios" in contenido
    assert "proyectos" in contenido


def test_diagnostico_sanitiza_contrasena():
    uri = "postgresql+psycopg://usuario:REEMPLAZAR_SECRETO_LOCAL@localhost:5432/calidad_web"
    sanitizada = limpiador.sanitizar_uri(uri)
    assert "secreto" not in sanitizada
    assert "***" in sanitizada


def test_verificacion_api_reporta_registros_antiguos(monkeypatch):
    monkeypatch.setattr(
        limpiador,
        "obtener_conteos_api",
        lambda: {"resumen.ejecuciones": 9, "api.ejecuciones": 9},
    )
    with pytest.raises(limpiador.LimpiezaCancelada):
        limpiador.verificar_api_limpia()


def test_api_apagada_no_cancela_verificacion(monkeypatch, capsys):
    def sin_api():
        raise limpiador.requests.ConnectionError("conexion rechazada")

    monkeypatch.setattr(limpiador, "obtener_conteos_api", sin_api)
    limpiador.verificar_api_limpia()
    assert "Aviso: API no disponible" in capsys.readouterr().out


def test_limpieza_demo_elimina_pendientes_despues_de_detener(app, tmp_path, monkeypatch):
    usuario_id, hash_original, evidencia = crear_datos_operativos(app, tmp_path)
    Ejecucion.query.first().estado = "en_ejecucion"
    db.session.commit()
    monkeypatch.setattr(limpiador, "PROJECT_ROOT", tmp_path)
    pasos = []
    monkeypatch.setattr(limpiador, "pedir_confirmacion", lambda: pasos.append("confirmar"))
    monkeypatch.setattr(limpiador, "detener_servicios_locales", lambda: pasos.append("detener"))

    def respaldo():
        assert pasos == ["confirmar", "detener"]
        assert Ejecucion.query.count() == 1
        pasos.append("respaldo")
        return tmp_path / "respaldo.json"

    monkeypatch.setattr(limpiador, "crear_respaldo", respaldo)
    # La limpieza normal no debe necesitar red ni credenciales de la API.
    monkeypatch.setattr(limpiador, "obtener_conteos_api", lambda: pytest.fail("Consulta HTTP inesperada"))
    limpiador.comando_limpiar(app, detener_servicios=True)
    assert pasos == ["confirmar", "detener", "respaldo"]
    assert limpiador.verificar_limpieza() == (True, [])
    assert db.session.get(Usuario, usuario_id).contrasena_hash == hash_original
    assert not evidencia.exists()
    limpiador.comando_verificar(app)
    # Repetir la limpieza con el sistema ya vacio tambien funciona.
    monkeypatch.setattr(limpiador, "crear_respaldo", lambda: tmp_path / "segundo.json")
    limpiador.comando_limpiar(app, confirmar=False)


@pytest.mark.parametrize("fallo", ["confirmacion", "detencion", "respaldo"])
def test_fallos_previos_no_borran_datos(app, tmp_path, monkeypatch, fallo):
    _, _, evidencia = crear_datos_operativos(app, tmp_path)
    monkeypatch.setattr(limpiador, "PROJECT_ROOT", tmp_path)
    pasos = []

    def paso(nombre):
        def ejecutar():
            pasos.append(nombre)
            if nombre == fallo:
                raise limpiador.LimpiezaCancelada(nombre)
            return tmp_path / "respaldo.json"
        return ejecutar

    monkeypatch.setattr(limpiador, "pedir_confirmacion", paso("confirmacion"))
    monkeypatch.setattr(limpiador, "detener_servicios_locales", paso("detencion"))
    monkeypatch.setattr(limpiador, "crear_respaldo", paso("respaldo"))
    with pytest.raises(limpiador.LimpiezaCancelada):
        limpiador.comando_limpiar(app, detener_servicios=True)
    assert pasos[-1] == fallo
    assert Proyecto.query.count() == 1
    assert evidencia.exists()


def test_ruta_invalida_se_rechaza_antes_de_borrar(app, tmp_path, monkeypatch):
    crear_datos_operativos(app, tmp_path)
    monkeypatch.setattr(limpiador, "PROJECT_ROOT", tmp_path)
    app.config["RUTA_EVIDENCIAS"] = str(tmp_path / "ajena")
    monkeypatch.setattr(limpiador, "detener_servicios_locales", lambda: pytest.fail("Detencion inesperada"))
    with pytest.raises(limpiador.LimpiezaCancelada):
        limpiador.comando_limpiar(app, confirmar=False, detener_servicios=True)
    assert Proyecto.query.count() == 1


def test_respaldo_sqlite_incluye_wal(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from sqlalchemy.engine import make_url
    import sqlite3

    origen = tmp_path / "calidad_web_dev.db"
    monkeypatch.setattr(limpiador, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(limpiador, "db", SimpleNamespace(engine=SimpleNamespace(url=make_url(f"sqlite:///{origen}"))))
    with sqlite3.connect(origen) as fuente:
        fuente.execute("PRAGMA journal_mode=WAL")
        fuente.execute("CREATE TABLE ejemplo (valor TEXT)")
        fuente.execute("INSERT INTO ejemplo VALUES ('conservado')")
        fuente.commit()
        destino = limpiador.crear_respaldo()
        with sqlite3.connect(destino) as copia:
            assert copia.execute("SELECT valor FROM ejemplo").fetchall() == [("conservado",)]
