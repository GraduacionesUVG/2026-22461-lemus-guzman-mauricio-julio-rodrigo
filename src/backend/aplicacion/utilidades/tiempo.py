from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ZONA_HORARIA_PREDETERMINADA = "America/Guatemala"


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


def asegurar_utc(valor: datetime | None) -> datetime | None:
    if valor is None:
        return None
    if valor.tzinfo is None:
        return valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc)


def iso_utc(valor: datetime | None) -> str | None:
    utc = asegurar_utc(valor)
    if utc is None:
        return None
    return utc.isoformat(timespec="seconds").replace("+00:00", "Z")


def obtener_zona_horaria(nombre: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(nombre or ZONA_HORARIA_PREDETERMINADA)
    except ZoneInfoNotFoundError:
        return ZoneInfo(ZONA_HORARIA_PREDETERMINADA)


def convertir_a_zona(valor: datetime | None, zona_horaria: str | None = None) -> datetime | None:
    utc = asegurar_utc(valor)
    if utc is None:
        return None
    return utc.astimezone(obtener_zona_horaria(zona_horaria))
