import re


PATRONES_SENSIBLES = [
    re.compile(r"(?i)(password|contrasena|token|secret|authorization|cookie|api[_-]?key)=([^\s&]+)"),
    re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._\-]+"),
]


def sanitizar_texto(valor: object, limite: int = 500) -> str:
    texto = str(valor)[:limite]
    for patron in PATRONES_SENSIBLES:
        texto = patron.sub(lambda coincidencia: coincidencia.group(1) + "[redactado]", texto)
    return texto


def sanitizar_diccionario(valores: dict | None) -> dict:
    if not valores:
        return {}
    resultado = {}
    for clave, valor in valores.items():
        if any(palabra in clave.lower() for palabra in ["contrasena", "password", "token", "secret", "cookie", "authorization"]):
            resultado[clave] = "[redactado]"
        elif isinstance(valor, dict):
            resultado[clave] = sanitizar_diccionario(valor)
        else:
            resultado[clave] = sanitizar_texto(valor)
    return resultado
