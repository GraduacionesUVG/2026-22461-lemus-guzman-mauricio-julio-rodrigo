import time
from urllib.parse import urljoin
from uuid import UUID

from flask import current_app
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select
from selenium.webdriver.support import expected_conditions as condiciones
from selenium.webdriver.support.ui import WebDriverWait

from aplicacion.modelos import Secreto
from aplicacion.seguridad.cifrado import descifrar_valor
from aplicacion.utilidades.tiempo import ahora_utc, iso_utc


def construir_selector(selector: dict) -> tuple[str, str]:
    estrategia = selector["estrategia"]
    valor = selector["valor"]
    if estrategia == "id":
        return By.ID, valor
    if estrategia in {"nombre", "name"}:
        return By.NAME, valor
    if estrategia == "css":
        return By.CSS_SELECTOR, valor
    if estrategia == "xpath":
        return By.XPATH, valor
    if estrategia in {"texto", "texto_visible"}:
        return By.XPATH, f"//*[normalize-space(text())='{valor}']"
    if estrategia == "tag_name":
        return By.TAG_NAME, valor
    if estrategia == "class_name":
        return By.CLASS_NAME, valor
    if estrategia == "link_text":
        return By.LINK_TEXT, valor
    if estrategia == "partial_link_text":
        return By.PARTIAL_LINK_TEXT, valor
    return By.CSS_SELECTOR, valor


def crear_navegador():
    opciones = Options()
    if current_app.config["MODO_HEADLESS"]:
        opciones.add_argument("--headless=new")
    opciones.add_argument("--no-sandbox")
    opciones.add_argument("--disable-dev-shm-usage")
    opciones.add_argument("--window-size=1366,768")
    opciones.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    return webdriver.Chrome(options=opciones)


TECLAS = {
    "ENTER": Keys.ENTER,
    "TAB": Keys.TAB,
    "ESCAPE": Keys.ESCAPE,
    "SPACE": Keys.SPACE,
    "BACKSPACE": Keys.BACKSPACE,
    "DELETE": Keys.DELETE,
    "ARROW_UP": Keys.ARROW_UP,
    "ARROW_DOWN": Keys.ARROW_DOWN,
    "ARROW_LEFT": Keys.ARROW_LEFT,
    "ARROW_RIGHT": Keys.ARROW_RIGHT,
    "HOME": Keys.HOME,
    "END": Keys.END,
    "PAGE_UP": Keys.PAGE_UP,
    "PAGE_DOWN": Keys.PAGE_DOWN,
}


def comparar_valor(obtenido: str, esperado: str, comparacion: str = "contiene") -> bool:
    if comparacion == "igual":
        return obtenido == esperado
    return esperado in obtenido


def localizar(navegador, espera: WebDriverWait, selector: dict, condicion: str = "visible"):
    localizador = construir_selector(selector)
    if condicion == "presente":
        return espera.until(condiciones.presence_of_element_located(localizador))
    if condicion == "clickable":
        return espera.until(condiciones.element_to_be_clickable(localizador))
    return espera.until(condiciones.visibility_of_element_located(localizador))


def espera_para(tiempo_espera: int, configuracion: dict, navegador) -> WebDriverWait:
    timeout = int(configuracion.get("timeout_segundos", tiempo_espera))
    timeout = max(1, min(timeout, 60))
    return WebDriverWait(navegador, timeout)


def capturar_pantalla(navegador):
    try:
        WebDriverWait(navegador, 3).until(lambda driver: driver.execute_script("return document.readyState") in {"interactive", "complete"})
    except Exception:
        pass
    try:
        return navegador.get_screenshot_as_png()
    except WebDriverException:
        return None


def diagnostico_navegador(navegador) -> dict:
    datos = {}
    try:
        datos["url_actual"] = navegador.current_url
        datos["titulo"] = navegador.title
        datos["document_ready_state"] = navegador.execute_script("return document.readyState")
        datos["dom_body_caracteres"] = navegador.execute_script("return document.body ? document.body.innerText.length : 0")
        datos["dom_body_fragmento"] = navegador.execute_script("return document.body ? document.body.innerText.slice(0, 500) : ''")
    except Exception as exc:
        datos["diagnostico_error"] = str(exc)
    try:
        datos["errores_consola"] = [
            {"nivel": item.get("level"), "mensaje": item.get("message", "")[:500]}
            for item in navegador.get_log("browser")
            if item.get("level") in {"SEVERE", "WARNING"}
        ][-10:]
    except Exception:
        datos["errores_consola"] = []
    return datos


def datos_base_paso(paso, configuracion: dict, navegador=None) -> dict:
    datos = {
        "motor": "selenium",
        "accion": paso.tipo,
        "selector": configuracion.get("selector"),
        "usa_secreto": bool(configuracion.get("secreto")),
        "tipo_validacion": paso.tipo if paso.tipo.startswith(("validar", "esperar")) else None,
    }
    if navegador is not None:
        try:
            datos["url_actual"] = navegador.current_url
            datos["titulo"] = navegador.title
        except Exception:
            pass
    return datos


def es_fallo_funcional_por_espera(paso_tipo: str, exc: Exception) -> bool:
    return isinstance(exc, TimeoutException) and (paso_tipo.startswith("validar") or paso_tipo.startswith("esperar"))


def resolver_texto(configuracion: dict, proyecto_id: UUID | None) -> str:
    if "texto" in configuracion:
        return str(configuracion.get("texto", ""))
    secreto_nombre = configuracion.get("secreto")
    if secreto_nombre and proyecto_id:
        secreto = Secreto.query.filter_by(proyecto_id=proyecto_id, nombre=secreto_nombre).first()
        if secreto is None:
            raise RuntimeError("Secreto no encontrado para el proyecto")
        return descifrar_valor(current_app.config["CLAVE_CIFRADO_SECRETOS"], secreto.valor_cifrado)
    return ""


def ejecutar_navegar(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    destino = configuracion.get("url") or urljoin(url_base.rstrip("/") + "/", configuracion["ruta"].lstrip("/"))
    navegador.get(destino)
    return destino, navegador.current_url, "Navegacion ejecutada", None


def ejecutar_retroceder(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    navegador.back()
    return "Navegacion atras", navegador.current_url, "Navegacion atras ejecutada", None


def ejecutar_avanzar(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    navegador.forward()
    return "Navegacion adelante", navegador.current_url, "Navegacion adelante ejecutada", None


def ejecutar_recargar(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    navegador.refresh()
    return "Pagina recargada", navegador.current_url, "Recarga ejecutada", None


def ejecutar_escribir(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    elemento = localizar(navegador, espera, configuracion["selector"])
    elemento.clear()
    elemento.send_keys(resolver_texto(configuracion, proyecto_id))
    return "Texto ingresado", "Texto ingresado", "Paso ejecutado", None


def ejecutar_limpiar_campo(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    localizar(navegador, espera, configuracion["selector"]).clear()
    return "Campo limpio", "Campo limpio", "Campo limpiado", None


def ejecutar_hacer_clic(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    localizar(navegador, espera, configuracion["selector"], "clickable").click()
    return "Clic ejecutado", "Clic ejecutado", "Paso ejecutado", None


def ejecutar_doble_clic(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    ActionChains(navegador).double_click(localizar(navegador, espera, configuracion["selector"], "clickable")).perform()
    return "Doble clic ejecutado", "Doble clic ejecutado", "Paso ejecutado", None


def ejecutar_clic_derecho(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    ActionChains(navegador).context_click(localizar(navegador, espera, configuracion["selector"], "clickable")).perform()
    return "Clic derecho ejecutado", "Clic derecho ejecutado", "Paso ejecutado", None


def ejecutar_mover_mouse(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    ActionChains(navegador).move_to_element(localizar(navegador, espera, configuracion["selector"])).perform()
    return "Mouse sobre elemento", "Mouse sobre elemento", "Paso ejecutado", None


def ejecutar_seleccionar_opcion(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    seleccion = Select(localizar(navegador, espera, configuracion["selector"]))
    metodo = configuracion["metodo"]
    valor = str(configuracion["valor"])
    if metodo == "valor":
        seleccion.select_by_value(valor)
    elif metodo == "texto_visible":
        seleccion.select_by_visible_text(valor)
    else:
        seleccion.select_by_index(int(valor))
    return f"Opcion {valor}", seleccion.first_selected_option.text, "Opcion seleccionada", None


def ejecutar_marcar_checkbox(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    elemento = localizar(navegador, espera, configuracion["selector"], "clickable")
    if not elemento.is_selected():
        elemento.click()
    return "Checkbox marcado", "Checkbox marcado" if elemento.is_selected() else "Checkbox no marcado", "Paso ejecutado", None


def ejecutar_desmarcar_checkbox(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    elemento = localizar(navegador, espera, configuracion["selector"], "clickable")
    if elemento.is_selected():
        elemento.click()
    return "Checkbox desmarcado", "Checkbox desmarcado" if not elemento.is_selected() else "Checkbox marcado", "Paso ejecutado", None


def ejecutar_presionar_tecla(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    tecla = TECLAS[configuracion["tecla"]]
    if configuracion.get("selector"):
        localizar(navegador, espera, configuracion["selector"]).send_keys(tecla)
    else:
        ActionChains(navegador).send_keys(tecla).perform()
    return configuracion["tecla"], configuracion["tecla"], "Tecla presionada", None


def ejecutar_scroll(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    modalidad = configuracion["modalidad"]
    if modalidad == "hasta_elemento":
        ActionChains(navegador).scroll_to_element(localizar(navegador, espera, configuracion["selector"])).perform()
    elif modalidad == "arriba":
        ActionChains(navegador).scroll_by_amount(0, -700).perform()
    else:
        ActionChains(navegador).scroll_by_amount(0, 700).perform()
    return modalidad, modalidad, "Scroll ejecutado", None


def ejecutar_esperar_elemento(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    localizar(navegador, espera, configuracion["selector"], configuracion.get("condicion", "visible"))
    return configuracion.get("condicion", "visible"), "Elemento encontrado", "Espera completada", None


def ejecutar_esperar_texto(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    espera.until(condiciones.text_to_be_present_in_element(construir_selector(configuracion["selector"]), configuracion["texto_esperado"]))
    return configuracion["texto_esperado"], configuracion["texto_esperado"], "Texto encontrado", None


def ejecutar_esperar_url(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    texto_url = configuracion["texto_url"]
    if configuracion.get("comparacion", "contiene") == "igual":
        espera.until(condiciones.url_to_be(texto_url))
    else:
        espera.until(condiciones.url_contains(texto_url))
    return texto_url, navegador.current_url, "URL esperada encontrada", None


def ejecutar_validar_texto(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    elemento = localizar(navegador, espera, configuracion["selector"])
    esperado = configuracion["texto_esperado"]
    obtenido = elemento.text
    if not comparar_valor(obtenido, esperado, configuracion.get("comparacion", "contiene")):
        return esperado, obtenido, "El texto esperado no coincide con el texto visible", capturar_pantalla(navegador)
    return esperado, obtenido, "Validacion exitosa", None


def ejecutar_validar_elemento_visible(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    localizar(navegador, espera, configuracion["selector"], "visible")
    return "Elemento visible", "Elemento visible", "Validacion exitosa", None


def ejecutar_validar_elemento_existente(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    localizar(navegador, espera, configuracion["selector"], "presente")
    return "Elemento existente", "Elemento existente", "Validacion exitosa", None


def ejecutar_validar_elemento_habilitado(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    elemento = localizar(navegador, espera, configuracion["selector"], "presente")
    if not elemento.is_enabled():
        return "Elemento habilitado", "Elemento deshabilitado", "El elemento no esta habilitado", capturar_pantalla(navegador)
    return "Elemento habilitado", "Elemento habilitado", "Validacion exitosa", None


def ejecutar_validar_elemento_seleccionado(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    elemento = localizar(navegador, espera, configuracion["selector"], "presente")
    if not elemento.is_selected():
        return "Elemento seleccionado", "Elemento no seleccionado", "El elemento no esta seleccionado", capturar_pantalla(navegador)
    return "Elemento seleccionado", "Elemento seleccionado", "Validacion exitosa", None


def ejecutar_validar_atributo(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    elemento = localizar(navegador, espera, configuracion["selector"], "presente")
    esperado = str(configuracion["valor_esperado"])
    obtenido = elemento.get_attribute(configuracion["atributo"]) or ""
    if not comparar_valor(obtenido, esperado, configuracion.get("comparacion", "contiene")):
        return esperado, obtenido, "El atributo esperado no coincide", capturar_pantalla(navegador)
    return esperado, obtenido, "Validacion exitosa", None


def ejecutar_validar_url(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    esperado = configuracion["url_esperada"]
    obtenido = navegador.current_url
    if not comparar_valor(obtenido, esperado, configuracion.get("comparacion", "contiene")):
        return esperado, obtenido, "La URL esperada no coincide", capturar_pantalla(navegador)
    return esperado, obtenido, "Validacion exitosa", None


def ejecutar_validar_titulo(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    esperado = configuracion["titulo_esperado"]
    obtenido = navegador.title
    if not comparar_valor(obtenido, esperado, configuracion.get("comparacion", "contiene")):
        return esperado, obtenido, "El titulo esperado no coincide", capturar_pantalla(navegador)
    return esperado, obtenido, "Validacion exitosa", None


def ejecutar_aceptar_alerta(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    alerta = espera.until(condiciones.alert_is_present())
    texto = alerta.text
    alerta.accept()
    return "Alerta aceptada", texto, "Alerta aceptada", None


def ejecutar_cancelar_alerta(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    alerta = espera.until(condiciones.alert_is_present())
    texto = alerta.text
    alerta.dismiss()
    return "Alerta cancelada", texto, "Alerta cancelada", None


def ejecutar_validar_texto_alerta(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    alerta = espera.until(condiciones.alert_is_present())
    esperado = configuracion["texto_esperado"]
    obtenido = alerta.text
    if not comparar_valor(obtenido, esperado, configuracion.get("comparacion", "contiene")):
        return esperado, obtenido, "El texto de la alerta no coincide", capturar_pantalla(navegador)
    return esperado, obtenido, "Validacion exitosa", None


def ejecutar_cambiar_a_nueva_pestana(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    navegador.switch_to.window(navegador.window_handles[-1])
    return "Ultima pestana", navegador.current_url, "Cambio de pestana ejecutado", None


def ejecutar_cambiar_a_pestana(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    indice = int(configuracion["indice"])
    if indice >= len(navegador.window_handles):
        raise RuntimeError("El indice de pestana no existe")
    navegador.switch_to.window(navegador.window_handles[indice])
    return f"Pestana {indice}", navegador.current_url, "Cambio de pestana ejecutado", None


def ejecutar_cerrar_pestana(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    navegador.close()
    if navegador.window_handles:
        navegador.switch_to.window(navegador.window_handles[-1])
    return "Pestana cerrada", navegador.current_url if navegador.window_handles else "", "Pestana cerrada", None


def ejecutar_capturar_evidencia(navegador, espera, url_base: str, configuracion: dict, proyecto_id: UUID | None) -> tuple[str, str, str, bytes | None]:
    return configuracion.get("nombre", "captura_manual"), navegador.current_url, "Evidencia capturada", navegador.get_screenshot_as_png()


EJECUTORES = {
    "navegar": ejecutar_navegar,
    "retroceder": ejecutar_retroceder,
    "avanzar": ejecutar_avanzar,
    "recargar": ejecutar_recargar,
    "escribir": ejecutar_escribir,
    "limpiar_campo": ejecutar_limpiar_campo,
    "hacer_clic": ejecutar_hacer_clic,
    "doble_clic": ejecutar_doble_clic,
    "clic_derecho": ejecutar_clic_derecho,
    "mover_mouse": ejecutar_mover_mouse,
    "seleccionar_opcion": ejecutar_seleccionar_opcion,
    "marcar_checkbox": ejecutar_marcar_checkbox,
    "desmarcar_checkbox": ejecutar_desmarcar_checkbox,
    "presionar_tecla": ejecutar_presionar_tecla,
    "scroll": ejecutar_scroll,
    "esperar_elemento": ejecutar_esperar_elemento,
    "esperar_texto": ejecutar_esperar_texto,
    "esperar_url": ejecutar_esperar_url,
    "validar_texto": ejecutar_validar_texto,
    "validar_elemento_visible": ejecutar_validar_elemento_visible,
    "validar_elemento_existente": ejecutar_validar_elemento_existente,
    "validar_elemento_habilitado": ejecutar_validar_elemento_habilitado,
    "validar_elemento_seleccionado": ejecutar_validar_elemento_seleccionado,
    "validar_atributo": ejecutar_validar_atributo,
    "validar_url": ejecutar_validar_url,
    "validar_titulo": ejecutar_validar_titulo,
    "aceptar_alerta": ejecutar_aceptar_alerta,
    "cancelar_alerta": ejecutar_cancelar_alerta,
    "validar_texto_alerta": ejecutar_validar_texto_alerta,
    "cambiar_a_nueva_pestana": ejecutar_cambiar_a_nueva_pestana,
    "cambiar_a_pestana": ejecutar_cambiar_a_pestana,
    "cerrar_pestana": ejecutar_cerrar_pestana,
    "capturar_evidencia": ejecutar_capturar_evidencia,
}


def ejecutar_caso_selenium(url_base: str, pasos: list, tiempo_espera: int, proyecto_id: UUID | None = None) -> list[dict]:
    resultados = []
    navegador = crear_navegador()
    try:
        for paso in pasos:
            inicio = time.perf_counter()
            inicio_fecha = ahora_utc()
            configuracion = paso.configuracion
            estado = "exitosa"
            esperado = ""
            obtenido = ""
            mensaje = "Paso ejecutado"
            captura = None
            nombre_evidencia = None
            datos_tecnicos = datos_base_paso(paso, configuracion, navegador)
            try:
                espera = espera_para(tiempo_espera, configuracion, navegador)
                ejecutor = EJECUTORES.get(paso.tipo)
                if ejecutor is None:
                    raise RuntimeError("Tipo de paso no soportado")
                esperado, obtenido, mensaje, captura = ejecutor(navegador, espera, url_base, configuracion, proyecto_id)
                if paso.tipo.startswith("validar") and mensaje != "Validacion exitosa":
                    estado = "fallida"
                if paso.tipo == "capturar_evidencia":
                    nombre_evidencia = configuracion.get("nombre")
                datos_tecnicos.update(datos_base_paso(paso, configuracion, navegador))
                datos_tecnicos["resultado_localizacion"] = "ejecutado"
            except Exception as exc:
                estado = "fallida" if isinstance(exc, AssertionError) or es_fallo_funcional_por_espera(paso.tipo, exc) else "error_tecnico"
                mensaje = str(exc)
                datos_tecnicos.update(diagnostico_navegador(navegador))
                datos_tecnicos["diagnostico_error"] = str(exc)
                captura = capturar_pantalla(navegador)
            duracion = int((time.perf_counter() - inicio) * 1000)
            fin_fecha = ahora_utc()
            datos_tecnicos.update({
                "estado": estado,
                "esperado": esperado,
                "obtenido": obtenido,
                "duracion_milisegundos": duracion,
                "fecha_inicio": iso_utc(inicio_fecha),
                "fecha_fin": iso_utc(fin_fecha),
                "captura_generada": captura is not None,
            })
            resultados.append({
                "paso": paso,
                "estado": estado,
                "esperado": esperado,
                "obtenido": obtenido,
                "mensaje": mensaje,
                "duracion_milisegundos": duracion,
                "captura": captura,
                "nombre_evidencia": nombre_evidencia,
                "datos": datos_tecnicos,
            })
            if estado != "exitosa" and not paso.continuar_si_falla:
                break
    finally:
        navegador.quit()
    return resultados
