import hashlib
from pathlib import Path
from uuid import UUID

from flask import current_app

from aplicacion.extensiones import db
from aplicacion.modelos import Evidencia


def registrar_archivo_evidencia(ejecucion_id: UUID, resultado_paso_id: UUID | None, nombre_archivo: str, contenido: bytes, tipo: str = "captura") -> Evidencia:
    raiz = Path(current_app.config["RUTA_EVIDENCIAS"])
    carpeta = raiz / str(ejecucion_id)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / nombre_archivo
    ruta.write_bytes(contenido)
    hash_sha256 = hashlib.sha256(contenido).hexdigest()
    evidencia = Evidencia(
        ejecucion_id=ejecucion_id,
        resultado_paso_id=resultado_paso_id,
        tipo=tipo,
        nombre_archivo=nombre_archivo,
        ruta_relativa=f"{ejecucion_id}/{nombre_archivo}",
        tipo_contenido="image/png" if nombre_archivo.endswith(".png") else "text/plain",
        tamano_bytes=len(contenido),
        hash_sha256=hash_sha256,
    )
    db.session.add(evidencia)
    db.session.flush()
    return evidencia
