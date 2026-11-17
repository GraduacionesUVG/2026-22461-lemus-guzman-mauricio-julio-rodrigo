from uuid import UUID
from selenium.common.exceptions import TimeoutException
from aplicacion.extensiones import db
from aplicacion.modelos import Evidencia, Notificacion, PasoCasoPrueba, Secreto
from aplicacion.seguridad.cifrado import descifrar_valor
from aplicacion.automatizacion.selenium_servicio import resolver_texto
from aplicacion.automatizacion.selenium_servicio import ejecutar_caso_selenium


class RespuestaHttpFalsa:
    status_code = 200
    text = "ok"


class RespuestaHttpErrorFalsa:
    status_code = 500
    text = "error"


def test_inicio_sesion_y_sesion_actual(cliente):
    respuesta = cliente.post("/api/autenticacion/iniciar-sesion", json={"correo": "usuario@example.invalid", "contrasena": "Contrasena123"})
    assert respuesta.status_code == 200
    assert respuesta.json["usuario"]["correo"] == "usuario@example.invalid"
    sesion = cliente.get("/api/autenticacion/sesion-actual")
    assert sesion.status_code == 200


def test_administrador_crea_usuario_qa_y_actualiza_tour(cliente_autenticado, cliente):
    creado = cliente_autenticado.post(
        "/api/usuarios",
        json={"nombre": "QA Demo", "correo": "qa@example.com", "contrasena": "Temporal123", "roles": ["qa"], "activo": True},
    )
    assert creado.status_code == 201
    assert creado.json["roles"] == ["qa"]
    sesion = cliente.post("/api/autenticacion/iniciar-sesion", json={"correo": "qa@example.com", "contrasena": "Temporal123"})
    assert sesion.status_code == 200
    assert sesion.json["usuario"]["tour_completado"] is False
    preferencias = cliente.patch("/api/autenticacion/preferencias", json={"tour_completado": True})
    assert preferencias.status_code == 200
    assert preferencias.json["usuario"]["tour_completado"] is True


def test_qa_no_puede_administrar_usuarios(cliente_autenticado, cliente):
    cliente_autenticado.post(
        "/api/usuarios",
        json={"nombre": "QA Restringido", "correo": "qa-restringido@example.com", "contrasena": "Temporal123", "roles": ["qa"], "activo": True},
    )
    cliente.post("/api/autenticacion/iniciar-sesion", json={"correo": "qa-restringido@example.com", "contrasena": "Temporal123"})
    respuesta = cliente.get("/api/usuarios")
    assert respuesta.status_code == 403


def test_creacion_proyecto_entorno_y_secreto_sin_valor(cliente_autenticado):
    proyecto = cliente_autenticado.post("/api/proyectos", json={"nombre": "Portal QA", "descripcion": "Demo"}).json
    entorno = cliente_autenticado.post(f"/api/proyectos/{proyecto['id']}/entornos", json={"nombre": "pruebas", "url_base": "http://localhost:5000/demo-objetivo"}).json
    secreto = cliente_autenticado.post(f"/api/proyectos/{proyecto['id']}/secretos", json={"nombre": "contrasena_demo", "tipo": "password", "valor": "secreto"}).json
    assert entorno["nombre"] == "pruebas"
    assert "valor" not in secreto
    assert "valor_cifrado" not in secreto
    assert Secreto.query.count() == 1


def test_secreto_se_crea_actualiza_y_resuelve_sin_exponer_valor(app, cliente_autenticado):
    proyecto = cliente_autenticado.post("/api/proyectos", json={"nombre": "Veltrix Commerce campaña experimental", "descripcion": "Demo"}).json
    creado = cliente_autenticado.post(
        f"/api/proyectos/{proyecto['id']}/secretos",
        json={"nombre": "veltrix_owner_password", "tipo": "password", "valor": "primera-clave"},
    )
    assert creado.status_code == 201
    assert "valor" not in creado.json
    assert "valor_cifrado" not in creado.json

    registro = Secreto.query.filter_by(proyecto_id=UUID(proyecto["id"]), nombre="veltrix_owner_password").first()
    assert registro is not None
    assert "primera-clave" not in registro.valor_cifrado
    assert descifrar_valor(app.config["CLAVE_CIFRADO_SECRETOS"], registro.valor_cifrado) == "primera-clave"

    actualizado = cliente_autenticado.post(
        f"/api/proyectos/{proyecto['id']}/secretos",
        json={"nombre": "veltrix_owner_password", "tipo": "password", "valor": "clave-actualizada"},
    )
    assert actualizado.status_code == 201
    assert actualizado.json["id"] == creado.json["id"]
    assert Secreto.query.filter_by(proyecto_id=UUID(proyecto["id"]), nombre="veltrix_owner_password").count() == 1

    listado = cliente_autenticado.get(f"/api/proyectos/{proyecto['id']}/secretos").json["elementos"]
    assert listado[0]["nombre"] == "veltrix_owner_password"
    assert "valor" not in listado[0]
    assert "valor_cifrado" not in listado[0]

    db.session.remove()
    resuelto = resolver_texto({"secreto": "veltrix_owner_password"}, UUID(proyecto["id"]))
    assert resuelto == "clave-actualizada"


def test_usuario_sin_rol_autorizado_no_administra_secretos(cliente_autenticado, cliente):
    proyecto = cliente_autenticado.post("/api/proyectos", json={"nombre": "Portal permisos", "descripcion": "Demo"}).json
    cliente_autenticado.post(
        "/api/usuarios",
        json={"nombre": "Responsable", "correo": "responsable@example.com", "contrasena": "Temporal123", "roles": ["responsable"], "activo": True},
    )
    cliente.post("/api/autenticacion/iniciar-sesion", json={"correo": "responsable@example.com", "contrasena": "Temporal123"})
    respuesta = cliente.post(
        f"/api/proyectos/{proyecto['id']}/secretos",
        json={"nombre": "veltrix_owner_password", "tipo": "password", "valor": "no-autorizado"},
    )
    assert respuesta.status_code == 403
    assert Secreto.query.count() == 0


def test_yaml_valida_y_no_requiere_secretos(cliente_autenticado):
    contenido = """
version: 1
proyecto:
  nombre: Portal
entornos:
  - nombre: pruebas
    url_base: http://localhost:5000
casos_prueba:
  - nombre: Login
    pasos:
      - orden: 1
        tipo: navegar
        nombre: Abrir
        configuracion:
          ruta: /login
"""
    respuesta = cliente_autenticado.post("/api/configuraciones-yaml/validar", json={"contenido": contenido})
    assert respuesta.status_code == 200
    assert respuesta.json["valido"] is True


def test_yaml_importa_caso_con_revision_humana(cliente_autenticado):
    contenido = """
version: 1
proyecto:
  nombre: Portal revision
entornos:
  - nombre: pruebas
    url_base: http://localhost:5000
casos_prueba:
  - nombre: Login revisable
    requiere_revision_humana: true
    pasos:
      - orden: 1
        tipo: navegar
        nombre: Abrir
        configuracion:
          ruta: /login
"""
    respuesta = cliente_autenticado.post("/api/configuraciones-yaml/importar", json={"contenido": contenido})
    assert respuesta.status_code == 201
    casos = cliente_autenticado.get("/api/casos-prueba").json["elementos"]
    assert any(caso["nombre"] == "Login revisable" and caso["requiere_revision_humana"] is True for caso in casos)


def test_importacion_yaml_aplica_configuracion(cliente_autenticado):
    contenido = """
version: 1
proyecto:
  nombre: Portal importado
entornos:
  - nombre: pruebas
    url_base: http://localhost:5000
casos_prueba:
  - nombre: Login
    pasos:
      - orden: 1
        tipo: navegar
        nombre: Abrir
        configuracion:
          ruta: /login
monitores:
  - nombre: Salud
    tipo: http
    configuracion:
      ruta: /health
      metodo: GET
      estados_esperados:
        - 200
pipelines:
  - nombre: Validacion
    pasos:
      - orden: 1
        tipo: monitor
        referencia: Salud
      - orden: 2
        tipo: caso_prueba
        referencia: Login
programaciones:
  - nombre: Diaria
    pipeline: Validacion
    frecuencia:
      tipo: diaria
      hora: "06:00"
"""
    respuesta = cliente_autenticado.post("/api/configuraciones-yaml/importar", json={"contenido": contenido})
    assert respuesta.status_code == 201
    assert respuesta.json["aplicado"] is True
    proyectos = cliente_autenticado.get("/api/proyectos").json
    assert any(proyecto["nombre"] == "Portal importado" for proyecto in proyectos["elementos"])


def test_previsualizacion_yaml_compara_con_proyecto_existente(cliente_autenticado):
    proyecto = cliente_autenticado.post("/api/proyectos", json={"nombre": "Portal preview", "descripcion": "Demo"}).json
    cliente_autenticado.post(f"/api/proyectos/{proyecto['id']}/entornos", json={"nombre": "pruebas", "url_base": "http://localhost:5000"})
    contenido = """
version: 1
proyecto:
  nombre: Portal preview
entornos:
  - nombre: pruebas
    url_base: http://localhost:5000
  - nombre: staging
    url_base: http://localhost:5001
casos_prueba:
  - nombre: Login
    pasos:
      - orden: 1
        tipo: navegar
        nombre: Abrir
        configuracion:
          ruta: /login
"""
    respuesta = cliente_autenticado.post("/api/configuraciones-yaml/previsualizar", json={"contenido": contenido})
    assert respuesta.status_code == 200
    assert respuesta.json["valido"] is True
    assert respuesta.json["comparacion"]["proyecto"]["accion"] == "crear_copia"
    assert respuesta.json["comparacion"]["entornos"]["coincidentes"] == ["pruebas"]
    assert respuesta.json["comparacion"]["entornos"]["nuevos"] == ["staging"]
    assert respuesta.json["resumen"]["pasos_casos_prueba"] == 1


def test_canal_notificacion_no_expone_configuracion(cliente_autenticado):
    proyecto = cliente_autenticado.post("/api/proyectos", json={"nombre": "Portal con alertas", "descripcion": "Demo"}).json
    canal = cliente_autenticado.post(
        f"/api/proyectos/{proyecto['id']}/canales-notificacion",
        json={"nombre": "Webhook QA", "tipo": "webhook", "configuracion": {"url": "http://localhost:5000/demo-objetivo/api/estado", "metodo": "POST"}},
    )
    assert canal.status_code == 201
    assert "configuracion" not in canal.json
    assert "configuracion_cifrada" not in canal.json
    listado = cliente_autenticado.get(f"/api/proyectos/{proyecto['id']}/canales-notificacion").json
    assert listado["elementos"][0]["nombre"] == "Webhook QA"


def test_notificacion_webhook_reintenta_ante_error(monkeypatch, cliente_autenticado):
    def solicitud_falsa(*args, **kwargs):
        return RespuestaHttpErrorFalsa()

    monkeypatch.setattr("aplicacion.monitoreo.servicio.requests.request", lambda *args, **kwargs: RespuestaHttpFalsa())
    monkeypatch.setattr("aplicacion.notificaciones.servicio.requests.request", solicitud_falsa)
    monkeypatch.setattr("aplicacion.notificaciones.servicio.time.sleep", lambda *args: None)
    proyecto = cliente_autenticado.post("/api/proyectos", json={"nombre": "Portal reintentos", "descripcion": "Demo"}).json
    entorno = cliente_autenticado.post(f"/api/proyectos/{proyecto['id']}/entornos", json={"nombre": "pruebas", "url_base": "http://localhost:5000"}).json
    monitor = cliente_autenticado.post("/api/monitores", json={"proyecto_id": proyecto["id"], "entorno_id": entorno["id"], "nombre": "Falla", "tipo": "http", "configuracion": {"ruta": "/health", "metodo": "GET", "estados_esperados": [503]}}).json
    cliente_autenticado.post(
        f"/api/proyectos/{proyecto['id']}/canales-notificacion",
        json={"nombre": "Webhook", "tipo": "webhook", "configuracion": {"url": "http://localhost:5000/notificar", "metodo": "POST"}},
    )
    pipeline = cliente_autenticado.post("/api/pipelines", json={"proyecto_id": proyecto["id"], "nombre": "Pipeline fallo", "pasos": [{"orden": 1, "tipo": "monitor", "nombre": "Falla", "monitor_id": monitor["id"]}]}).json
    ejecucion = cliente_autenticado.post(f"/api/pipelines/{pipeline['id']}/ejecutar", json={"entorno_id": entorno["id"], "procesar_ahora": True}).json
    notificacion = Notificacion.query.filter_by(ejecucion_id=UUID(ejecucion["id"])).first()
    assert notificacion.estado == "fallida"
    assert notificacion.intentos == 3


def test_pipeline_monitor_guarda_resultado(monkeypatch, cliente_autenticado):
    def solicitud_falsa(*args, **kwargs):
        return RespuestaHttpFalsa()

    monkeypatch.setattr("aplicacion.monitoreo.servicio.requests.request", solicitud_falsa)
    proyecto = cliente_autenticado.post("/api/proyectos", json={"nombre": "Portal pipeline", "descripcion": "Demo"}).json
    entorno = cliente_autenticado.post(f"/api/proyectos/{proyecto['id']}/entornos", json={"nombre": "pruebas", "url_base": "http://localhost:5000"}).json
    monitor = cliente_autenticado.post("/api/monitores", json={"proyecto_id": proyecto["id"], "entorno_id": entorno["id"], "nombre": "Salud", "tipo": "http", "configuracion": {"ruta": "/health", "metodo": "GET", "estados_esperados": [200]}}).json
    pipeline = cliente_autenticado.post("/api/pipelines", json={"proyecto_id": proyecto["id"], "nombre": "Validacion monitor", "pasos": [{"orden": 1, "tipo": "monitor", "nombre": "Salud", "monitor_id": monitor["id"]}]}).json
    ejecucion = cliente_autenticado.post(f"/api/pipelines/{pipeline['id']}/ejecutar", json={"entorno_id": entorno["id"], "procesar_ahora": True}).json
    assert ejecucion["estado"] == "exitosa"
    assert ejecucion["resultados"][0]["estado"] == "exitosa"


def test_monitor_base_datos_usa_secreto_cifrado(cliente_autenticado):
    proyecto = cliente_autenticado.post("/api/proyectos", json={"nombre": "Portal datos", "descripcion": "Demo"}).json
    entorno = cliente_autenticado.post(f"/api/proyectos/{proyecto['id']}/entornos", json={"nombre": "pruebas", "url_base": "http://localhost:5000"}).json
    secreto = cliente_autenticado.post(f"/api/proyectos/{proyecto['id']}/secretos", json={"nombre": "conexion_sqlite", "tipo": "cadena_conexion", "valor": "sqlite://"}).json
    monitor = cliente_autenticado.post(
        "/api/monitores",
        json={"proyecto_id": proyecto["id"], "entorno_id": entorno["id"], "nombre": "Base local", "tipo": "base_datos", "configuracion": {"consulta": "SELECT 1", "secreto_cadena_conexion_id": secreto["id"]}},
    ).json
    resultado = cliente_autenticado.post(f"/api/monitores/{monitor['id']}/ejecutar", json={"entorno_id": entorno["id"]})
    assert resultado.status_code == 200
    assert resultado.json["estado"] == "exitosa"
    assert resultado.json["mensaje"] == "Monitor de base de datos ejecutado"


def test_monitor_api_valida_fragmento_de_respuesta(monkeypatch):
    from aplicacion.monitoreo.servicio import ejecutar_monitor_api

    class Respuesta:
        status_code = 200
        text = '{"name":"Aurora Boutique"}'

    monkeypatch.setattr("aplicacion.monitoreo.servicio.requests.request", lambda *args, **kwargs: Respuesta())
    exitoso = ejecutar_monitor_api({"url": "http://example.test", "texto_esperado": "Aurora Boutique"})
    fallido = ejecutar_monitor_api({"url": "http://example.test", "texto_esperado": "Producto inexistente"})
    assert exitoso["estado"] == "exitosa"
    assert fallido["estado"] == "fallida"


def test_monitor_api_indisponible_es_fallo_controlado(monkeypatch):
    import requests

    from aplicacion.monitoreo.servicio import ejecutar_monitor_api

    def solicitud_falla(*args, **kwargs):
        raise requests.ConnectionError("connection refused password=secreto")

    monkeypatch.setattr("aplicacion.monitoreo.servicio.requests.request", solicitud_falla)
    resultado = ejecutar_monitor_api({"url": "http://127.0.0.1:8766/health", "estados_esperados": [200], "tiempo_espera": 1})
    assert resultado["estado"] == "fallida"
    assert resultado["obtenido"] == "Servicio no disponible"
    assert resultado["datos"]["clasificacion"] == "servicio_indisponible"
    assert "secreto" not in resultado["datos"]["error_sanitizado"]


def test_worker_persiste_resultado_de_monitor_indisponible(monkeypatch, cliente_autenticado):
    import requests

    def solicitud_falla(*args, **kwargs):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr("aplicacion.monitoreo.servicio.requests.request", solicitud_falla)
    proyecto = cliente_autenticado.post("/api/proyectos", json={"nombre": "Portal monitor indisponible", "descripcion": "Demo"}).json
    entorno = cliente_autenticado.post(f"/api/proyectos/{proyecto['id']}/entornos", json={"nombre": "demo", "url_base": "http://localhost:5000"}).json
    monitor = cliente_autenticado.post(
        "/api/monitores",
        json={"proyecto_id": proyecto["id"], "entorno_id": entorno["id"], "nombre": "Servicio auxiliar", "tipo": "api", "configuracion": {"url": "http://127.0.0.1:8766/health", "estados_esperados": [200]}},
    ).json
    pipeline = cliente_autenticado.post(
        "/api/pipelines",
        json={"proyecto_id": proyecto["id"], "nombre": "Pipeline fallo controlado", "detener_ante_fallo": False, "pasos": [{"orden": 1, "tipo": "monitor", "nombre": "CP-10", "monitor_id": monitor["id"], "continuar_si_falla": True}]},
    ).json
    ejecucion = cliente_autenticado.post(f"/api/pipelines/{pipeline['id']}/ejecutar", json={"entorno_id": entorno["id"], "procesar_ahora": True}).json
    assert ejecucion["estado"] == "fallida"
    assert ejecucion["error_tecnico"] is None
    assert ejecucion["resultados"][0]["estado"] == "fallida"
    assert ejecucion["resultados"][0]["obtenido"] == "Servicio no disponible"
    assert ejecucion["resultados"][0]["datos_tecnicos_sanitizados"]["clasificacion"] == "servicio_indisponible"
    assert ejecucion["alertas"][0]["tipo"] == "pipeline"


def test_worker_persiste_diagnostico_si_falla_antes_de_resultados(monkeypatch, cliente_autenticado):
    def paso_roto(*args, **kwargs):
        raise RuntimeError("fallo interno token=secreto")

    monkeypatch.setattr("aplicacion.trabajadores.servicio.ejecutar_paso_monitor", paso_roto)
    proyecto = cliente_autenticado.post("/api/proyectos", json={"nombre": "Portal diagnostico tecnico", "descripcion": "Demo"}).json
    entorno = cliente_autenticado.post(f"/api/proyectos/{proyecto['id']}/entornos", json={"nombre": "demo", "url_base": "http://localhost:5000"}).json
    monitor = cliente_autenticado.post("/api/monitores", json={"proyecto_id": proyecto["id"], "entorno_id": entorno["id"], "nombre": "Salud", "tipo": "http", "configuracion": {"ruta": "/health"}}).json
    pipeline = cliente_autenticado.post("/api/pipelines", json={"proyecto_id": proyecto["id"], "nombre": "Pipeline roto", "pasos": [{"orden": 1, "tipo": "monitor", "nombre": "Salud", "monitor_id": monitor["id"]}]}).json
    ejecucion = cliente_autenticado.post(f"/api/pipelines/{pipeline['id']}/ejecutar", json={"entorno_id": entorno["id"], "procesar_ahora": True}).json
    assert ejecucion["estado"] == "error_tecnico"
    assert "secreto" not in ejecucion["error_tecnico"]
    assert ejecucion["resultados"][0]["tipo"] == "inicializacion"
    assert ejecucion["resultados"][0]["estado"] == "error_tecnico"
    assert ejecucion["alertas"][0]["tipo"] == "error_tecnico"


def test_programacion_previsualiza_y_actualiza_siguiente_ejecucion(cliente_autenticado):
    proyecto = cliente_autenticado.post("/api/proyectos", json={"nombre": "Portal programado", "descripcion": "Demo"}).json
    entorno = cliente_autenticado.post(f"/api/proyectos/{proyecto['id']}/entornos", json={"nombre": "pruebas", "url_base": "http://localhost:5000"}).json
    pipeline = cliente_autenticado.post("/api/pipelines", json={"proyecto_id": proyecto["id"], "nombre": "Validacion programada", "pasos": []}).json
    preview = cliente_autenticado.post(
        "/api/programaciones/previsualizar",
        json={"tipo_frecuencia": "minutos", "configuracion_frecuencia": {"cada": 10, "entorno_id": entorno["id"]}},
    )
    assert preview.status_code == 200
    assert "siguiente_ejecucion" in preview.json
    programacion = cliente_autenticado.post(
        "/api/programaciones",
        json={"pipeline_id": pipeline["id"], "nombre": "Cada diez minutos", "tipo_frecuencia": "minutos", "configuracion_frecuencia": {"cada": 10, "entorno_id": entorno["id"]}},
    ).json
    actualizada = cliente_autenticado.patch(
        f"/api/programaciones/{programacion['id']}",
        json={"nombre": "Revision diaria", "tipo_frecuencia": "diaria", "configuracion_frecuencia": {"hora": "06:30", "entorno_id": entorno["id"]}, "activo": False},
    ).json
    assert actualizada["nombre"] == "Revision diaria"
    assert actualizada["tipo_frecuencia"] == "diaria"
    assert actualizada["activo"] is False
    assert actualizada["siguiente_ejecucion"] != programacion["siguiente_ejecucion"]


def test_reporte_evaluacion_csv_descargable(cliente_autenticado):
    cliente_autenticado.post("/api/proyectos", json={"nombre": "Portal reporte", "descripcion": "Demo"})
    respuesta = cliente_autenticado.get("/api/metricas/reporte-evaluacion.csv")
    assert respuesta.status_code == 200
    assert respuesta.mimetype == "text/csv"
    assert "proyecto,pipelines,ejecuciones" in respuesta.text
    assert "Portal reporte" in respuesta.text


def test_metricas_responden(cliente_autenticado):
    respuesta = cliente_autenticado.get("/api/metricas/resumen")
    assert respuesta.status_code == 200
    assert "cobertura_modulos_criticos" in respuesta.json


def test_constructor_backend_acepta_acciones_selenium_ampliadas(cliente_autenticado):
    proyecto = cliente_autenticado.post("/api/proyectos", json={"nombre": "Portal constructor", "descripcion": "Demo"}).json
    secreto = cliente_autenticado.post(f"/api/proyectos/{proyecto['id']}/secretos", json={"nombre": "contrasena_demo", "tipo": "password", "valor": "demo"}).json
    pasos = [
        {"orden": 1, "tipo": "navegar", "nombre": "Abrir componentes", "configuracion": {"ruta": "/componentes"}},
        {"orden": 2, "tipo": "esperar_elemento", "nombre": "Esperar campo", "configuracion": {"selector": {"estrategia": "id", "valor": "campo-texto"}, "condicion": "visible", "timeout_segundos": 10}},
        {"orden": 3, "tipo": "escribir", "nombre": "Escribir texto", "configuracion": {"selector": {"estrategia": "id", "valor": "campo-texto"}, "texto": "demo"}},
        {"orden": 4, "tipo": "escribir", "nombre": "Escribir secreto", "configuracion": {"selector": {"estrategia": "id", "valor": "campo-texto"}, "secreto": "contrasena_demo"}},
        {"orden": 5, "tipo": "hacer_clic", "nombre": "Presionar boton", "configuracion": {"selector": {"estrategia": "id", "valor": "boton-demo"}}},
        {"orden": 6, "tipo": "seleccionar_opcion", "nombre": "Seleccionar", "configuracion": {"selector": {"estrategia": "id", "valor": "select-demo"}, "metodo": "valor", "valor": "uno"}},
        {"orden": 7, "tipo": "marcar_checkbox", "nombre": "Marcar", "configuracion": {"selector": {"estrategia": "id", "valor": "checkbox-demo"}}},
        {"orden": 8, "tipo": "presionar_tecla", "nombre": "Enter", "configuracion": {"tecla": "ENTER"}},
        {"orden": 9, "tipo": "validar_url", "nombre": "Validar URL", "configuracion": {"url_esperada": "/componentes", "comparacion": "contiene"}},
        {"orden": 10, "tipo": "validar_atributo", "nombre": "Validar atributo", "configuracion": {"selector": {"estrategia": "id", "valor": "campo-texto"}, "atributo": "data-estado", "valor_esperado": "listo", "comparacion": "igual"}},
    ]
    respuesta = cliente_autenticado.post("/api/casos-prueba", json={"proyecto_id": proyecto["id"], "nombre": "Flujo visual", "prioridad": "alta", "pasos": pasos})
    assert respuesta.status_code == 201
    assert len(respuesta.json["pasos"]) == len(pasos)
    assert secreto["nombre"] == "contrasena_demo"


def test_yaml_valida_acciones_selenium_nuevas(cliente_autenticado):
    contenido = """
version: 1
proyecto:
  nombre: Portal acciones nuevas
entornos:
  - nombre: pruebas
    url_base: http://localhost:5000/demo-objetivo
casos_prueba:
  - nombre: Componentes
    pasos:
      - orden: 1
        tipo: navegar
        nombre: Abrir
        configuracion:
          ruta: /componentes
      - orden: 2
        tipo: seleccionar_opcion
        nombre: Seleccionar
        configuracion:
          selector:
            estrategia: id
            valor: select-demo
          metodo: valor
          valor: uno
      - orden: 3
        tipo: validar_atributo
        nombre: Atributo
        configuracion:
          selector:
            estrategia: id
            valor: campo-texto
          atributo: data-estado
          valor_esperado: listo
          comparacion: igual
"""
    respuesta = cliente_autenticado.post("/api/configuraciones-yaml/validar", json={"contenido": contenido})
    assert respuesta.status_code == 200
    assert respuesta.json["valido"] is True


def test_rechaza_accion_desconocida_y_configuracion_incompleta(cliente_autenticado):
    proyecto = cliente_autenticado.post("/api/proyectos", json={"nombre": "Portal rechazos", "descripcion": "Demo"}).json
    desconocida = cliente_autenticado.post("/api/casos-prueba", json={"proyecto_id": proyecto["id"], "nombre": "Malo", "pasos": [{"orden": 1, "tipo": "ejecutar_python", "nombre": "No", "configuracion": {}}]})
    incompleta = cliente_autenticado.post("/api/casos-prueba", json={"proyecto_id": proyecto["id"], "nombre": "Incompleto", "pasos": [{"orden": 1, "tipo": "hacer_clic", "nombre": "Clic", "configuracion": {"selector": {"estrategia": "id"}}}]})
    assert desconocida.status_code == 400
    assert incompleta.status_code == 400


def test_backend_acepta_todas_las_acciones_selenium(cliente_autenticado):
    proyecto = cliente_autenticado.post("/api/proyectos", json={"nombre": "Portal todas acciones", "descripcion": "Demo"}).json
    cliente_autenticado.post(f"/api/proyectos/{proyecto['id']}/secretos", json={"nombre": "contrasena_demo", "tipo": "password", "valor": "demo"})
    selector = {"estrategia": "id", "valor": "campo-texto"}
    pasos = [
        {"orden": 1, "tipo": "navegar", "nombre": "navegar", "configuracion": {"ruta": "/componentes"}},
        {"orden": 2, "tipo": "retroceder", "nombre": "retroceder", "configuracion": {}},
        {"orden": 3, "tipo": "avanzar", "nombre": "avanzar", "configuracion": {}},
        {"orden": 4, "tipo": "recargar", "nombre": "recargar", "configuracion": {}},
        {"orden": 5, "tipo": "escribir", "nombre": "escribir texto", "configuracion": {"selector": selector, "texto": "demo"}},
        {"orden": 6, "tipo": "escribir", "nombre": "escribir secreto", "configuracion": {"selector": selector, "secreto": "contrasena_demo"}},
        {"orden": 7, "tipo": "limpiar_campo", "nombre": "limpiar", "configuracion": {"selector": selector}},
        {"orden": 8, "tipo": "hacer_clic", "nombre": "clic", "configuracion": {"selector": {"estrategia": "id", "valor": "boton-demo"}}},
        {"orden": 9, "tipo": "doble_clic", "nombre": "doble", "configuracion": {"selector": {"estrategia": "id", "valor": "boton-demo"}}},
        {"orden": 10, "tipo": "clic_derecho", "nombre": "derecho", "configuracion": {"selector": {"estrategia": "id", "valor": "boton-demo"}}},
        {"orden": 11, "tipo": "mover_mouse", "nombre": "hover", "configuracion": {"selector": selector}},
        {"orden": 12, "tipo": "seleccionar_opcion", "nombre": "select", "configuracion": {"selector": {"estrategia": "id", "valor": "select-demo"}, "metodo": "valor", "valor": "uno"}},
        {"orden": 13, "tipo": "marcar_checkbox", "nombre": "marcar", "configuracion": {"selector": {"estrategia": "id", "valor": "checkbox-demo"}}},
        {"orden": 14, "tipo": "desmarcar_checkbox", "nombre": "desmarcar", "configuracion": {"selector": {"estrategia": "id", "valor": "checkbox-demo"}}},
        {"orden": 15, "tipo": "presionar_tecla", "nombre": "tecla", "configuracion": {"tecla": "ENTER"}},
        {"orden": 16, "tipo": "scroll", "nombre": "scroll", "configuracion": {"modalidad": "abajo"}},
        {"orden": 17, "tipo": "esperar_elemento", "nombre": "esperar elemento", "configuracion": {"selector": selector, "condicion": "visible", "timeout_segundos": 10}},
        {"orden": 18, "tipo": "esperar_texto", "nombre": "esperar texto", "configuracion": {"selector": {"estrategia": "css", "valor": "main h1"}, "texto_esperado": "Panel principal", "timeout_segundos": 10}},
        {"orden": 19, "tipo": "esperar_url", "nombre": "esperar url", "configuracion": {"texto_url": "/componentes", "comparacion": "contiene", "timeout_segundos": 10}},
        {"orden": 20, "tipo": "validar_texto", "nombre": "validar texto", "configuracion": {"selector": {"estrategia": "css", "valor": "main h1"}, "texto_esperado": "Panel principal", "comparacion": "igual"}},
        {"orden": 21, "tipo": "validar_elemento_visible", "nombre": "visible", "configuracion": {"selector": selector}},
        {"orden": 22, "tipo": "validar_elemento_existente", "nombre": "existente", "configuracion": {"selector": selector}},
        {"orden": 23, "tipo": "validar_elemento_habilitado", "nombre": "habilitado", "configuracion": {"selector": selector}},
        {"orden": 24, "tipo": "validar_elemento_seleccionado", "nombre": "seleccionado", "configuracion": {"selector": {"estrategia": "id", "valor": "checkbox-demo"}}},
        {"orden": 25, "tipo": "validar_atributo", "nombre": "atributo", "configuracion": {"selector": selector, "atributo": "data-estado", "valor_esperado": "listo", "comparacion": "igual"}},
        {"orden": 26, "tipo": "validar_url", "nombre": "url", "configuracion": {"url_esperada": "/componentes", "comparacion": "contiene"}},
        {"orden": 27, "tipo": "validar_titulo", "nombre": "titulo", "configuracion": {"titulo_esperado": "Componentes Demo", "comparacion": "igual"}},
        {"orden": 28, "tipo": "aceptar_alerta", "nombre": "aceptar alerta", "configuracion": {}},
        {"orden": 29, "tipo": "cancelar_alerta", "nombre": "cancelar alerta", "configuracion": {}},
        {"orden": 30, "tipo": "validar_texto_alerta", "nombre": "texto alerta", "configuracion": {"texto_esperado": "Alerta de prueba", "comparacion": "contiene"}},
        {"orden": 31, "tipo": "cambiar_a_nueva_pestana", "nombre": "nueva pestana", "configuracion": {}},
        {"orden": 32, "tipo": "cambiar_a_pestana", "nombre": "pestana", "configuracion": {"indice": 0}},
        {"orden": 33, "tipo": "cerrar_pestana", "nombre": "cerrar", "configuracion": {}},
        {"orden": 34, "tipo": "capturar_evidencia", "nombre": "captura", "configuracion": {"nombre": "captura_manual"}},
    ]
    respuesta = cliente_autenticado.post("/api/casos-prueba", json={"proyecto_id": proyecto["id"], "nombre": "Todas las acciones", "pasos": pasos})
    assert respuesta.status_code == 201
    assert [paso["tipo"] for paso in respuesta.json["pasos"]] == [paso["tipo"] for paso in pasos]


class ElementoFalso:
    def __init__(self, texto="", atributo=None, seleccionado=False, al_hacer_clic=None):
        self.text = texto
        self.atributo = atributo or {}
        self.seleccionado = seleccionado
        self.valor = ""
        self.al_hacer_clic = al_hacer_clic

    def clear(self):
        self.valor = ""

    def send_keys(self, valor):
        self.valor += str(valor)

    def click(self):
        self.seleccionado = not self.seleccionado
        if self.al_hacer_clic:
            self.al_hacer_clic()

    def is_selected(self):
        return self.seleccionado

    def is_enabled(self):
        return True

    def is_displayed(self):
        return True

    def get_attribute(self, nombre):
        return self.atributo.get(nombre)


class NavegadorFalso:
    def __init__(self):
        self.current_url = "about:blank"
        self.title = "Componentes Demo"
        self.window_handles = ["principal"]
        self.switch_to = SimpleSwitchFalso(self)
        self.titulo = ElementoFalso(texto="Panel principal")
        self.elementos = {
            ("id", "campo-texto"): ElementoFalso(atributo={"data-estado": "listo"}),
            ("id", "checkbox-demo"): ElementoFalso(seleccionado=False),
            ("css selector", "main h1"): self.titulo,
            ("id", "correo"): ElementoFalso(),
            ("id", "contrasena"): ElementoFalso(),
            ("css selector", "button[type='submit']"): ElementoFalso(al_hacer_clic=lambda: setattr(self.titulo, "text", "Panel principal")),
            ("id", "boton-demo"): ElementoFalso(al_hacer_clic=lambda: setattr(self.titulo, "text", "Panel principal")),
        }

    def get(self, url):
        self.current_url = url

    def back(self):
        self.current_url = "about:blank"

    def forward(self):
        self.current_url = "http://localhost:5000/demo-objetivo/componentes"

    def refresh(self):
        pass

    def find_element(self, by, value):
        return self.elementos[(by, value)]

    def get_screenshot_as_png(self):
        return b"captura"

    def execute_script(self, script):
        if "document.readyState" in script:
            return "complete"
        if "document.body ? document.body.innerText.length" in script:
            return len(self.titulo.text)
        if "document.body ? document.body.innerText.slice" in script:
            return self.titulo.text
        return ""

    def get_log(self, nombre):
        return []

    def quit(self):
        pass


class SimpleSwitchFalso:
    def __init__(self, navegador):
        self.navegador = navegador

    def window(self, identificador):
        self.navegador.current_url = f"http://localhost:5000/demo-objetivo/{identificador}"


class EsperaFalsa:
    def __init__(self, navegador):
        self.navegador = navegador

    def until(self, condicion):
        return condicion(self.navegador)


def test_motor_selenium_ejecuta_acciones_basicas_con_navegador_falso(monkeypatch, app):
    navegador = NavegadorFalso()
    monkeypatch.setattr("aplicacion.automatizacion.selenium_servicio.crear_navegador", lambda: navegador)
    monkeypatch.setattr("aplicacion.automatizacion.selenium_servicio.espera_para", lambda tiempo, configuracion, driver: EsperaFalsa(driver))
    with app.app_context():
        from aplicacion.seguridad.cifrado import cifrar_valor

        proyecto_id = UUID(int=1)
        db.session.add(Secreto(id=UUID(int=2), proyecto_id=proyecto_id, nombre="contrasena_demo", tipo="password", valor_cifrado=cifrar_valor(app.config["CLAVE_CIFRADO_SECRETOS"], "secreto")))
        db.session.commit()
        pasos = [
            PasoCasoPrueba(orden=1, tipo="navegar", nombre="Abrir", configuracion={"ruta": "/componentes"}),
            PasoCasoPrueba(orden=2, tipo="escribir", nombre="Texto", configuracion={"selector": {"estrategia": "id", "valor": "campo-texto"}, "texto": "hola"}),
            PasoCasoPrueba(orden=3, tipo="escribir", nombre="Secreto", configuracion={"selector": {"estrategia": "id", "valor": "campo-texto"}, "secreto": "contrasena_demo"}),
            PasoCasoPrueba(orden=4, tipo="hacer_clic", nombre="Click", configuracion={"selector": {"estrategia": "id", "valor": "boton-demo"}}),
            PasoCasoPrueba(orden=5, tipo="marcar_checkbox", nombre="Check", configuracion={"selector": {"estrategia": "id", "valor": "checkbox-demo"}}),
            PasoCasoPrueba(orden=6, tipo="validar_url", nombre="URL", configuracion={"url_esperada": "/componentes", "comparacion": "contiene"}),
            PasoCasoPrueba(orden=7, tipo="validar_atributo", nombre="Atributo", configuracion={"selector": {"estrategia": "id", "valor": "campo-texto"}, "atributo": "data-estado", "valor_esperado": "listo", "comparacion": "igual"}),
            PasoCasoPrueba(orden=8, tipo="validar_texto", nombre="Texto correcto", configuracion={"selector": {"estrategia": "css", "valor": "main h1"}, "texto_esperado": "Panel principal", "comparacion": "igual"}),
            PasoCasoPrueba(orden=9, tipo="validar_texto", nombre="Texto fallido", configuracion={"selector": {"estrategia": "css", "valor": "main h1"}, "texto_esperado": "Otro panel", "comparacion": "igual"}),
        ]
        resultados = ejecutar_caso_selenium("http://localhost:5000/demo-objetivo", pasos, 5, proyecto_id)
    assert [resultado["estado"] for resultado in resultados[:-1]] == ["exitosa"] * 8
    assert resultados[-1]["estado"] == "fallida"
    assert resultados[-1]["captura"] == b"captura"


class EsperaTimeoutFalsa:
    def until(self, condicion):
        raise TimeoutException("mensaje no encontrado")


def test_timeout_de_espera_selenium_se_clasifica_como_fallo_funcional(monkeypatch, app):
    navegador = NavegadorFalso()
    monkeypatch.setattr("aplicacion.automatizacion.selenium_servicio.crear_navegador", lambda: navegador)
    monkeypatch.setattr("aplicacion.automatizacion.selenium_servicio.espera_para", lambda tiempo, configuracion, driver: EsperaTimeoutFalsa())
    with app.app_context():
        pasos = [
            PasoCasoPrueba(
                orden=1,
                tipo="esperar_elemento",
                nombre="Esperar mensaje funcional",
                configuracion={"selector": {"estrategia": "css", "valor": "[role='alert']"}, "condicion": "visible", "timeout_segundos": 1},
            ),
        ]
        resultados = ejecutar_caso_selenium("http://localhost:5000/demo-objetivo", pasos, 1)
    assert resultados[0]["estado"] == "fallida"
    assert resultados[0]["captura"] == b"captura"
    assert resultados[0]["datos"]["document_ready_state"] == "complete"


def configurar_navegador_falso(monkeypatch):
    navegador = NavegadorFalso()
    monkeypatch.setattr("aplicacion.automatizacion.selenium_servicio.crear_navegador", lambda: navegador)
    monkeypatch.setattr("aplicacion.automatizacion.selenium_servicio.espera_para", lambda tiempo, configuracion, driver: EsperaFalsa(driver))
    return navegador


def test_worker_ejecuta_caso_visual_exitoso_y_guarda_evidencia(monkeypatch, cliente_autenticado):
    configurar_navegador_falso(monkeypatch)
    proyecto = cliente_autenticado.post("/api/proyectos", json={"nombre": "Portal worker exitoso", "descripcion": "Demo"}).json
    entorno = cliente_autenticado.post(f"/api/proyectos/{proyecto['id']}/entornos", json={"nombre": "demo", "url_base": "http://localhost:5000/demo-objetivo"}).json
    cliente_autenticado.post(f"/api/proyectos/{proyecto['id']}/secretos", json={"nombre": "contrasena_demo", "tipo": "password", "valor": "demo"})
    caso = cliente_autenticado.post("/api/casos-prueba", json={"proyecto_id": proyecto["id"], "nombre": "Login visual exitoso", "pasos": [
        {"orden": 1, "tipo": "navegar", "nombre": "Abrir", "configuracion": {"ruta": "/login"}},
        {"orden": 2, "tipo": "esperar_elemento", "nombre": "Esperar formulario", "configuracion": {"selector": {"estrategia": "id", "valor": "correo"}, "condicion": "visible", "timeout_segundos": 10}},
        {"orden": 3, "tipo": "escribir", "nombre": "Usuario", "configuracion": {"selector": {"estrategia": "id", "valor": "correo"}, "texto": "demo@example.com"}},
        {"orden": 4, "tipo": "escribir", "nombre": "Clave", "configuracion": {"selector": {"estrategia": "id", "valor": "contrasena"}, "secreto": "contrasena_demo"}},
        {"orden": 5, "tipo": "hacer_clic", "nombre": "Entrar", "configuracion": {"selector": {"estrategia": "css", "valor": "button[type='submit']"}}},
        {"orden": 6, "tipo": "validar_texto", "nombre": "Panel", "configuracion": {"selector": {"estrategia": "css", "valor": "main h1"}, "texto_esperado": "Panel principal", "comparacion": "igual"}},
        {"orden": 7, "tipo": "capturar_evidencia", "nombre": "Captura", "configuracion": {"nombre": "login_exitoso"}},
    ]}).json
    pipeline = cliente_autenticado.post("/api/pipelines", json={"proyecto_id": proyecto["id"], "nombre": "Pipeline visual", "pasos": [{"orden": 1, "tipo": "caso_prueba", "nombre": "Caso", "caso_prueba_id": caso["id"]}]}).json
    ejecucion = cliente_autenticado.post(f"/api/pipelines/{pipeline['id']}/ejecutar", json={"entorno_id": entorno["id"], "procesar_ahora": True}).json
    assert ejecucion["estado"] == "exitosa"
    assert len(ejecucion["resultados"]) == 7
    assert Evidencia.query.count() == 1


def test_worker_marca_validacion_fallida_y_genera_evidencia(monkeypatch, cliente_autenticado):
    configurar_navegador_falso(monkeypatch)
    proyecto = cliente_autenticado.post("/api/proyectos", json={"nombre": "Portal worker fallido", "descripcion": "Demo"}).json
    entorno = cliente_autenticado.post(f"/api/proyectos/{proyecto['id']}/entornos", json={"nombre": "demo", "url_base": "http://localhost:5000/demo-objetivo"}).json
    caso = cliente_autenticado.post("/api/casos-prueba", json={"proyecto_id": proyecto["id"], "nombre": "Validacion fallida", "pasos": [
        {"orden": 1, "tipo": "navegar", "nombre": "Abrir", "configuracion": {"ruta": "/login"}},
        {"orden": 2, "tipo": "validar_texto", "nombre": "Panel incorrecto", "configuracion": {"selector": {"estrategia": "css", "valor": "main h1"}, "texto_esperado": "No existe", "comparacion": "igual"}},
    ]}).json
    pipeline = cliente_autenticado.post("/api/pipelines", json={"proyecto_id": proyecto["id"], "nombre": "Pipeline fallido", "pasos": [{"orden": 1, "tipo": "caso_prueba", "nombre": "Caso", "caso_prueba_id": caso["id"]}]}).json
    ejecucion = cliente_autenticado.post(f"/api/pipelines/{pipeline['id']}/ejecutar", json={"entorno_id": entorno["id"], "procesar_ahora": True}).json
    assert ejecucion["estado"] == "fallida"
    assert ejecucion["resultados"][-1]["estado"] == "fallida"
    assert Evidencia.query.count() == 1
