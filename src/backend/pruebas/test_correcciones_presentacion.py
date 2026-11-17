import json
from pathlib import Path
from uuid import UUID

import pytest

from aplicacion.extensiones import db
from aplicacion.modelos import Alerta, Ejecucion, InformeEjecucion, Notificacion, ResultadoPaso
from aplicacion.trabajadores.servicio import procesar_ejecucion
from aplicacion.utilidades.presentacion import etiqueta_estado


@pytest.fixture()
def ejecucion(cliente_autenticado, app, tmp_path):
    # Una ruta relativa reproduce el fallo de send_file al resolver desde Flask.
    app.config['RUTA_INFORMES'] = str(tmp_path / 'informes')
    proyecto = cliente_autenticado.post('/api/proyectos', json={'nombre': 'Revision asesor'}).json
    entorno = cliente_autenticado.post(f"/api/proyectos/{proyecto['id']}/entornos", json={'nombre': 'local', 'url_base': 'http://localhost:5000'}).json
    pipeline = cliente_autenticado.post('/api/pipelines', json={'proyecto_id': proyecto['id'], 'nombre': 'Pruebas <QA> & reporte', 'pasos': []}).json
    corrida = Ejecucion(pipeline_id=UUID(pipeline['id']), entorno_id=UUID(entorno['id']), origen='manual', estado='en_ejecucion')
    db.session.add(corrida)
    db.session.commit()
    return corrida, proyecto


@pytest.mark.parametrize('estado', ['exitosa', 'fallida', 'error_tecnico'])
def test_finalizacion_envia_mensaje_y_pdf(estado, ejecucion, cliente_autenticado, monkeypatch, app):
    corrida, proyecto = ejecucion
    cliente_autenticado.post(f"/api/proyectos/{proyecto['id']}/canales-notificacion", json={
        'nombre': 'Discord', 'tipo': 'webhook', 'configuracion': {
            'url': 'https://discord.com/api/webhooks/000000000000000000/REEMPLAZAR_TOKEN_FICTICIO',
            'encabezados': {'Content-Type': 'application/json'},
        },
    })
    db.session.add(ResultadoPaso(ejecucion_id=corrida.id, tipo='monitor_http', estado=estado, mensaje='Diagnostico <HTTP> & QA'))
    db.session.commit()
    envios = []

    def enviar(metodo, url, **opciones):
        payload = json.loads(opciones['data']['payload_json'])
        archivo = opciones['files']['files[0]'][1].read()
        envios.append((payload, archivo, opciones['headers']))
        return type('Respuesta', (), {'status_code': 204})()

    monkeypatch.setattr('aplicacion.notificaciones.servicio.requests.request', enviar)
    procesar_ejecucion(corrida)
    assert corrida.estado == estado
    assert len(envios) == 1
    embed = envios[0][0]['embeds'][0]
    campos = {campo['name']: campo['value'] for campo in embed['fields']}
    assert embed['title'] == 'Sistema Integral de Calidad Web | Ejecución finalizada'
    assert campos['Estado final'] == etiqueta_estado(estado)
    assert 'Symbols not available' not in json.dumps(envios[0][0], ensure_ascii=False)
    assert envios[0][1].startswith(b'%PDF-')
    assert b'%%EOF' in envios[0][1][-30:]
    assert 'Content-Type' not in envios[0][2]
    assert Notificacion.query.filter_by(ejecucion_id=corrida.id).one().estado == 'enviada'


def test_error_notificacion_no_cambia_resultado(ejecucion, monkeypatch):
    corrida, _ = ejecucion
    monkeypatch.setattr('aplicacion.trabajadores.servicio.enviar_notificaciones_fallo', lambda _: (_ for _ in ()).throw(RuntimeError('Canal roto')))
    procesar_ejecucion(corrida)
    assert db.session.get(Ejecucion, corrida.id).estado == 'exitosa'
    assert Alerta.query.count() == 0


def test_pdf_visualizacion_descarga_y_archivo_corrupto(ejecucion, cliente_autenticado, app, tmp_path, monkeypatch):
    corrida, _ = ejecucion
    monkeypatch.chdir(tmp_path)
    app.config['RUTA_INFORMES'] = 'informes'
    db.session.add(ResultadoPaso(ejecucion_id=corrida.id, tipo='monitor_http', estado='fallida', mensaje='Error <HTTP> & respuesta ' * 1200))
    db.session.commit()
    ruta = f'/api/ejecuciones/{corrida.id}/informe/pdf'
    for sufijo, disposicion in [('', 'inline'), ('?descargar=1', 'attachment')]:
        respuesta = cliente_autenticado.get(ruta + sufijo)
        assert respuesta.status_code == 200
        assert respuesta.mimetype == 'application/pdf'
        assert respuesta.data.startswith(b'%PDF-')
        assert b'%%EOF' in respuesta.data[-30:]
        assert respuesta.headers['Content-Disposition'].startswith(disposicion)
    informe = InformeEjecucion.query.filter_by(ejecucion_id=corrida.id).one()
    Path('informes', informe.ruta_relativa).write_bytes(b'PDF incompleto')
    respuesta = cliente_autenticado.get(ruta)
    assert respuesta.status_code == 200
    assert respuesta.data.startswith(b'%PDF-')


@pytest.mark.parametrize('nivel', ['ejecucion', 'paso', 'alerta'])
def test_metricas_cuentan_y_actualizan_revisiones(nivel, ejecucion, cliente_autenticado):
    corrida, _ = ejecucion
    if nivel == 'paso':
        paso = ResultadoPaso(ejecucion_id=corrida.id, tipo='monitor_http', estado='fallida')
        db.session.add(paso)
        db.session.commit()
        ruta = f'/api/resultados-paso/{paso.id}/revision'
        campo, confirmado = 'clasificacion', 'confirmado'
    elif nivel == 'alerta':
        alerta = Alerta(ejecucion_id=corrida.id, tipo='pipeline', severidad='media')
        db.session.add(alerta)
        db.session.commit()
        ruta = f'/api/alertas/{alerta.id}/revisar'
        campo, confirmado = 'clasificacion_manual', 'confirmada'
    else:
        ruta = f'/api/ejecuciones/{corrida.id}/revision'
        campo, confirmado = 'clasificacion', 'confirmada'
    assert cliente_autenticado.get('/api/metricas/resumen').json['tasa_falsos_positivos'] == 0
    guardar = cliente_autenticado.patch if nivel == 'alerta' else cliente_autenticado.post
    assert guardar(ruta, json={campo: 'falso_positivo'}).status_code == 200
    assert cliente_autenticado.get('/api/metricas/resumen').json['tasa_falsos_positivos'] == 100
    assert guardar(ruta, json={campo: confirmado}).status_code == 200
    assert cliente_autenticado.get('/api/metricas/resumen').json['tasa_falsos_positivos'] == 0
