from datetime import datetime, timezone
from uuid import UUID

from aplicacion.extensiones import db
from aplicacion.informes.servicio import obtener_o_generar_informe
from aplicacion.modelos import Entorno, Ejecucion, Pipeline, Proyecto, ResultadoPaso
from aplicacion.notificaciones.servicio import enviar_webhook
from aplicacion.servicios.pipelines import calcular_siguiente_programacion
from aplicacion.utilidades.tiempo import convertir_a_zona, iso_utc


def test_timestamp_utc_se_presenta_en_guatemala():
    valor = datetime(2026, 10, 12, 7, 25, 39, tzinfo=timezone.utc)
    local = convertir_a_zona(valor, "America/Guatemala")
    assert local.hour == 1
    assert local.minute == 25
    assert local.day == 12
    assert iso_utc(valor) == "2026-10-12T07:25:39Z"


def test_conversion_cerca_de_medianoche_respeta_dia():
    valor = datetime(2026, 10, 12, 2, 15, tzinfo=timezone.utc)
    local = convertir_a_zona(valor, "America/Guatemala")
    assert local.day == 11
    assert local.hour == 20


def test_programacion_diaria_usa_zona_horaria_configurada():
    base = datetime(2026, 10, 12, 7, 25, tzinfo=timezone.utc)
    siguiente = calcular_siguiente_programacion(
        "diaria",
        {"hora": "06:30", "entorno_id": "00000000-0000-0000-0000-000000000001"},
        base=base,
        zona_horaria="America/Guatemala",
    )
    assert iso_utc(siguiente) == "2026-10-12T12:30:00Z"


def test_api_serializa_fechas_utc_con_z(cliente_autenticado):
    proyecto = cliente_autenticado.post("/api/proyectos", json={"nombre": "Sistema auditado"}).json
    entorno = cliente_autenticado.post(f"/api/proyectos/{proyecto['id']}/entornos", json={"nombre": "laboratorio", "url_base": "http://localhost:5000", "zona_horaria": "America/Guatemala"}).json
    pipeline = cliente_autenticado.post("/api/pipelines", json={"proyecto_id": proyecto["id"], "nombre": "Pipeline auditoria", "pasos": []}).json
    ejecucion = Ejecucion(
        pipeline_id=UUID(pipeline["id"]),
        entorno_id=UUID(entorno["id"]),
        origen="manual",
        estado="exitosa",
        fecha_encolado=datetime(2026, 10, 12, 7, 25, 39, tzinfo=timezone.utc),
        fecha_inicio=datetime(2026, 10, 12, 7, 26, tzinfo=timezone.utc),
        fecha_fin=datetime(2026, 10, 12, 7, 27, tzinfo=timezone.utc),
        duracion_milisegundos=60000,
    )
    db.session.add(ejecucion)
    db.session.commit()

    respuesta = cliente_autenticado.get(f"/api/ejecuciones/{ejecucion.id}").json
    assert respuesta["fecha_encolado"] == "2026-10-12T07:25:39Z"
    assert respuesta["duracion_milisegundos"] == 60000


def test_genera_informe_pdf_desde_registros_existentes(app):
    with app.app_context():
        proyecto = Proyecto(nombre="Sistema auditado", descripcion="")
        db.session.add(proyecto)
        db.session.flush()
        entorno = Entorno(proyecto_id=proyecto.id, nombre="laboratorio", url_base="http://localhost:5000", zona_horaria="America/Guatemala")
        pipeline = Pipeline(proyecto_id=proyecto.id, nombre="Pipeline auditoria")
        db.session.add_all([entorno, pipeline])
        db.session.flush()
        ejecucion = Ejecucion(
            pipeline_id=pipeline.id,
            entorno_id=entorno.id,
            origen="manual",
            estado="exitosa",
            fecha_inicio=datetime(2026, 10, 12, 7, 25, tzinfo=timezone.utc),
            fecha_fin=datetime(2026, 10, 12, 7, 26, tzinfo=timezone.utc),
            duracion_milisegundos=60000,
        )
        db.session.add(ejecucion)
        db.session.flush()
        db.session.add(ResultadoPaso(ejecucion_id=ejecucion.id, tipo="monitor_http", estado="exitosa", esperado="Estado 200", obtenido="Estado 200", mensaje="Monitor HTTP ejecutado"))
        db.session.commit()

        informe = obtener_o_generar_informe(ejecucion.id, regenerar=True)
        assert informe.nombre_archivo.endswith(".pdf")
        assert informe.tamano_bytes > 0


def test_discord_envia_pdf_como_multipart(monkeypatch, tmp_path):
    pdf = tmp_path / "informe.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    llamadas = []

    class Respuesta:
        status_code = 204

    def solicitud_falsa(metodo, url, **kwargs):
        llamadas.append({"metodo": metodo, "url": url, **kwargs})
        return Respuesta()

    monkeypatch.setattr("aplicacion.notificaciones.servicio.requests.request", solicitud_falsa)
    enviar_webhook({"url": "https://discord.com/api/webhooks/000000000000000000/REEMPLAZAR_TOKEN_FICTICIO", "metodo": "POST"}, "Alerta", pdf)

    assert llamadas[0]["data"]["payload_json"]
    assert "files[0]" in llamadas[0]["files"]
    assert "json" not in llamadas[0]
