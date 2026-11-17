from urllib.parse import urlparse
from uuid import UUID

from aplicacion.modelos import Secreto


TIPOS_PASO_SELENIUM = {
    "navegar",
    "retroceder",
    "avanzar",
    "recargar",
    "escribir",
    "limpiar_campo",
    "hacer_clic",
    "doble_clic",
    "clic_derecho",
    "mover_mouse",
    "seleccionar_opcion",
    "marcar_checkbox",
    "desmarcar_checkbox",
    "presionar_tecla",
    "scroll",
    "esperar_elemento",
    "esperar_texto",
    "esperar_url",
    "validar_texto",
    "validar_elemento_visible",
    "validar_elemento_existente",
    "validar_elemento_habilitado",
    "validar_elemento_seleccionado",
    "validar_atributo",
    "validar_url",
    "validar_titulo",
    "aceptar_alerta",
    "cancelar_alerta",
    "validar_texto_alerta",
    "cambiar_a_nueva_pestana",
    "cambiar_a_pestana",
    "cerrar_pestana",
    "capturar_evidencia",
}
ESTRATEGIAS_SELECTOR = {"id", "name", "nombre", "css", "xpath", "texto", "texto_visible", "tag_name", "class_name", "link_text", "partial_link_text"}
TIPOS_CON_SELECTOR = {
    "escribir",
    "limpiar_campo",
    "hacer_clic",
    "doble_clic",
    "clic_derecho",
    "mover_mouse",
    "seleccionar_opcion",
    "marcar_checkbox",
    "desmarcar_checkbox",
    "esperar_elemento",
    "esperar_texto",
    "validar_texto",
    "validar_elemento_visible",
    "validar_elemento_existente",
    "validar_elemento_habilitado",
    "validar_elemento_seleccionado",
    "validar_atributo",
}
TECLAS_PERMITIDAS = {"ENTER", "TAB", "ESCAPE", "SPACE", "BACKSPACE", "DELETE", "ARROW_UP", "ARROW_DOWN", "ARROW_LEFT", "ARROW_RIGHT", "HOME", "END", "PAGE_UP", "PAGE_DOWN"}
COMPARACIONES = {"igual", "contiene"}
CONDICIONES_ESPERA = {"presente", "visible", "clickable"}
METODOS_SELECCION = {"valor", "texto_visible", "indice"}
MODALIDADES_SCROLL = {"arriba", "abajo", "hasta_elemento"}


class ConfiguracionInvalida(ValueError):
    pass


def validar_url_web(url: str) -> None:
    partes = urlparse(url)
    if partes.scheme not in {"http", "https"} or not partes.netloc:
        raise ConfiguracionInvalida("La URL debe usar HTTP o HTTPS y contener un host valido.")


def validar_selector(configuracion: dict) -> None:
    selector = configuracion.get("selector") or {}
    if selector.get("estrategia") not in ESTRATEGIAS_SELECTOR or not str(selector.get("valor", "")).strip():
        raise ConfiguracionInvalida("El selector debe tener estrategia permitida y valor.")


def validar_timeout(configuracion: dict) -> None:
    if "timeout_segundos" not in configuracion:
        return
    try:
        timeout = int(configuracion["timeout_segundos"])
    except (TypeError, ValueError) as exc:
        raise ConfiguracionInvalida("El timeout debe ser numerico.") from exc
    if timeout < 1 or timeout > 60:
        raise ConfiguracionInvalida("El timeout debe estar entre 1 y 60 segundos.")


def validar_comparacion(configuracion: dict) -> None:
    if configuracion.get("comparacion", "contiene") not in COMPARACIONES:
        raise ConfiguracionInvalida("La comparacion indicada no es valida.")


def validar_secreto(configuracion: dict, proyecto_id: str | UUID | None) -> None:
    secreto_nombre = configuracion.get("secreto")
    if not secreto_nombre or proyecto_id is None:
        return
    secreto = Secreto.query.filter_by(proyecto_id=UUID(str(proyecto_id)), nombre=secreto_nombre).first()
    if secreto is None:
        raise ConfiguracionInvalida("El secreto seleccionado no pertenece al proyecto.")


def validar_pasos_caso(pasos: list[dict], proyecto_id: str | UUID | None = None) -> None:
    if not pasos:
        raise ConfiguracionInvalida("El caso requiere al menos un paso.")
    ordenes = [paso.get("orden") for paso in pasos]
    if sorted(ordenes) != list(range(1, len(pasos) + 1)):
        raise ConfiguracionInvalida("Los pasos deben tener orden consecutivo desde 1.")
    for paso in pasos:
        if not str(paso.get("nombre", "")).strip():
            raise ConfiguracionInvalida("Todos los pasos requieren nombre.")
        tipo = paso.get("tipo")
        if tipo not in TIPOS_PASO_SELENIUM:
            raise ConfiguracionInvalida(f"Tipo de paso no permitido: {tipo}.")
        configuracion = paso.get("configuracion") or {}
        if tipo in TIPOS_CON_SELECTOR:
            validar_selector(configuracion)
        validar_timeout(configuracion)
        if tipo == "navegar" and not (configuracion.get("ruta") or configuracion.get("url")):
            raise ConfiguracionInvalida("El paso navegar requiere ruta o URL.")
        if tipo == "navegar" and configuracion.get("url"):
            validar_url_web(configuracion["url"])
        if tipo == "escribir":
            tiene_texto = "texto" in configuracion and str(configuracion.get("texto", "")) != ""
            tiene_secreto = bool(configuracion.get("secreto"))
            if not tiene_texto and not tiene_secreto:
                raise ConfiguracionInvalida("El paso escribir requiere texto o secreto.")
            validar_secreto(configuracion, proyecto_id)
        if tipo == "seleccionar_opcion":
            if configuracion.get("metodo") not in METODOS_SELECCION or str(configuracion.get("valor", "")).strip() == "":
                raise ConfiguracionInvalida("El paso seleccionar_opcion requiere metodo y valor.")
            if configuracion.get("metodo") == "indice":
                try:
                    indice = int(configuracion["valor"])
                except (TypeError, ValueError) as exc:
                    raise ConfiguracionInvalida("El indice de seleccion debe ser numerico.") from exc
                if indice < 0:
                    raise ConfiguracionInvalida("El indice de seleccion no puede ser negativo.")
        if tipo == "presionar_tecla":
            if configuracion.get("tecla") not in TECLAS_PERMITIDAS:
                raise ConfiguracionInvalida("La tecla indicada no esta permitida.")
            if configuracion.get("selector"):
                validar_selector(configuracion)
        if tipo == "scroll":
            if configuracion.get("modalidad") not in MODALIDADES_SCROLL:
                raise ConfiguracionInvalida("La modalidad de scroll no es valida.")
            if configuracion.get("modalidad") == "hasta_elemento":
                validar_selector(configuracion)
        if tipo == "esperar_elemento" and configuracion.get("condicion") not in CONDICIONES_ESPERA:
            raise ConfiguracionInvalida("La condicion de espera no es valida.")
        if tipo in {"esperar_texto", "validar_texto", "validar_texto_alerta"} and "texto_esperado" not in configuracion:
            raise ConfiguracionInvalida(f"El paso {tipo} requiere texto esperado.")
        if tipo == "esperar_url":
            validar_comparacion(configuracion)
            if not str(configuracion.get("texto_url", "")).strip():
                raise ConfiguracionInvalida("El paso esperar_url requiere texto_url.")
        if tipo == "validar_texto" and "texto_esperado" not in configuracion:
            raise ConfiguracionInvalida("El paso validar_texto requiere texto esperado.")
        if tipo in {"validar_texto", "validar_atributo", "validar_url", "validar_titulo", "validar_texto_alerta"}:
            validar_comparacion(configuracion)
        if tipo == "validar_atributo" and (not str(configuracion.get("atributo", "")).strip() or "valor_esperado" not in configuracion):
            raise ConfiguracionInvalida("El paso validar_atributo requiere atributo y valor esperado.")
        if tipo == "validar_url" and not str(configuracion.get("url_esperada", "")).strip():
            raise ConfiguracionInvalida("El paso validar_url requiere URL o fragmento esperado.")
        if tipo == "validar_titulo" and "titulo_esperado" not in configuracion:
            raise ConfiguracionInvalida("El paso validar_titulo requiere titulo esperado.")
        if tipo == "cambiar_a_pestana":
            try:
                indice = int(configuracion.get("indice"))
            except (TypeError, ValueError) as exc:
                raise ConfiguracionInvalida("El indice de pestana debe ser numerico.") from exc
            if indice < 0:
                raise ConfiguracionInvalida("El indice de pestana no puede ser negativo.")


def validar_consulta_lectura(consulta: str) -> None:
    texto = consulta.strip().lower()
    prohibidas = ["insert", "update", "delete", "drop", "alter", "create", "truncate", ";", "grant", "revoke"]
    if not texto.startswith("select") or any(palabra in texto for palabra in prohibidas):
        raise ConfiguracionInvalida("La consulta debe ser una lectura segura con una sola sentencia SELECT.")
