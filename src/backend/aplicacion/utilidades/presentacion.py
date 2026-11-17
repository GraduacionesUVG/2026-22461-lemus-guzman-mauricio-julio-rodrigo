import re
from datetime import datetime

from aplicacion.utilidades.tiempo import convertir_a_zona


ETIQUETAS_ESTADO = {
    "exitosa": "Exitosa",
    "fallida": "Fallida",
    "error_tecnico": "Error técnico",
    "en_cola": "Pendiente",
    "pendiente": "Pendiente",
    "en_ejecucion": "En ejecución",
    "cancelada": "Cancelada",
    "enviada": "Enviada",
    "omitida": "Omitida",
    "revisada": "Revisada",
    "confirmada": "Confirmada",
    "confirmado": "Confirmado",
    "falso_positivo": "Falso positivo",
    "falso_negativo": "Falso negativo",
    "requiere_analisis": "Requiere análisis",
    "no_aplica": "No aplica",
    "alta": "Alta",
    "media": "Media",
    "baja": "Baja",
}

MARCADORES_TRAZA = (
    "stacktrace:",
    "symbols not available",
    "backtrace",
    "traceback (most recent call last)",
    "\tat ",
    "#0 0x",
)


def etiqueta_estado(estado: str | None) -> str:
    if not estado:
        return "No disponible"
    if estado in ETIQUETAS_ESTADO:
        return ETIQUETAS_ESTADO[estado]
    texto = str(estado).replace("_", " ")
    return texto[:1].upper() + texto[1:]


def resumir_diagnostico(texto: str | None, limite: int = 220) -> str:
    if not texto:
        return ""
    contenido = str(texto)
    minusculas = contenido.lower()
    posiciones = [minusculas.find(marcador) for marcador in MARCADORES_TRAZA]
    corte = min([posicion for posicion in posiciones if posicion > 0], default=len(contenido))
    util = re.sub(r"^\s*message:\s*", "", contenido[:corte], flags=re.IGNORECASE)
    lineas = [linea.strip() for linea in util.splitlines() if linea.strip()]
    if not lineas:
        return ""
    compacta = re.sub(r"\s+", " ", lineas[0])
    compacta = re.sub(r"^message:\s*", "", compacta, flags=re.IGNORECASE).strip()
    if len(compacta) > limite:
        return compacta[: limite - 1].rstrip() + "…"
    return compacta


def tiene_traza_extensa(texto: str | None) -> bool:
    if not texto:
        return False
    contenido = str(texto)
    return len(contenido) > 240 or len(contenido.splitlines()) > 3


def duracion_legible(milisegundos: int | float | None) -> str:
    if milisegundos is None:
        return "No disponible"
    valor = int(milisegundos)
    if valor < 1000:
        return f"{valor} ms"
    segundos_totales = valor / 1000
    if segundos_totales < 60:
        return f"{segundos_totales:.1f} s"
    minutos = int(segundos_totales // 60)
    segundos = int(round(segundos_totales % 60))
    if minutos < 60:
        return f"{minutos} min {segundos:02d} s"
    return f"{minutos // 60} h {minutos % 60:02d} min"


def fecha_legible(valor: datetime | None, zona: str | None = None) -> str:
    local = convertir_a_zona(valor, zona)
    if local is None:
        return "No disponible"
    return local.strftime("%d/%m/%Y, %I:%M:%S %p").replace("AM", "a.\u00a0m.").replace("PM", "p.\u00a0m.")


def recortar(texto: str | None, limite: int) -> str:
    contenido = str(texto or "")
    if len(contenido) <= limite:
        return contenido
    return contenido[: max(limite - 1, 0)].rstrip() + "…"
