import base64
import hashlib

from cryptography.fernet import Fernet


def crear_fernet(clave: str) -> Fernet:
    resumen = hashlib.sha256(clave.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(resumen))


def cifrar_valor(clave: str, valor: str) -> str:
    return crear_fernet(clave).encrypt(valor.encode("utf-8")).decode("utf-8")


def descifrar_valor(clave: str, valor_cifrado: str) -> str:
    return crear_fernet(clave).decrypt(valor_cifrado.encode("utf-8")).decode("utf-8")
