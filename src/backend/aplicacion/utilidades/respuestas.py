from uuid import UUID

from flask import jsonify

from aplicacion.utilidades.tiempo import iso_utc


def convertir_valor(valor):
    if isinstance(valor, UUID):
        return str(valor)
    if hasattr(valor, "isoformat"):
        return iso_utc(valor)
    return valor


def convertir_diccionario(registro: dict) -> dict:
    return {clave: convertir_valor(valor) for clave, valor in registro.items()}


def respuesta_exitosa(datos=None, codigo_estado: int = 200):
    return jsonify(datos if datos is not None else {}), codigo_estado


def respuesta_error(codigo: str, mensaje: str, codigo_estado: int = 400, detalles=None):
    cuerpo = {
        "codigo": codigo,
        "mensaje": mensaje,
        "detalles": detalles or {},
        "identificador_correlacion": "",
    }
    return jsonify(cuerpo), codigo_estado
