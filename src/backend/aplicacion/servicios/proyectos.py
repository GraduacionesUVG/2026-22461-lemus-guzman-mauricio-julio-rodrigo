from uuid import UUID

from flask import current_app

from aplicacion.auditoria.servicio import registrar_auditoria
from aplicacion.extensiones import db
from aplicacion.modelos import Entorno, ModuloObjetivo, Proyecto, Secreto
from aplicacion.seguridad.cifrado import cifrar_valor
from aplicacion.servicios.validaciones import ConfiguracionInvalida
from aplicacion.servicios.validaciones import validar_url_web


def crear_proyecto(datos: dict, usuario_id: str | None) -> Proyecto:
    proyecto = Proyecto(
        nombre=datos["nombre"],
        descripcion=datos.get("descripcion", ""),
        tecnologia_referencial=datos.get("tecnologia_referencial"),
        responsable=datos.get("responsable"),
        creado_por=UUID(usuario_id) if usuario_id else None,
    )
    db.session.add(proyecto)
    registrar_auditoria("crear", "proyecto", datos={"nombre": proyecto.nombre})
    db.session.commit()
    return proyecto


def actualizar_proyecto(proyecto_id: UUID, datos: dict) -> Proyecto:
    proyecto = Proyecto.query.get_or_404(proyecto_id)
    for campo in ["nombre", "descripcion", "tecnologia_referencial", "responsable", "activo"]:
        if campo in datos:
            setattr(proyecto, campo, datos[campo])
    registrar_auditoria("actualizar", "proyecto", str(proyecto.id), datos)
    db.session.commit()
    return proyecto


def crear_entorno(proyecto_id: UUID, datos: dict) -> Entorno:
    validar_url_web(datos["url_base"])
    entorno = Entorno(
        proyecto_id=proyecto_id,
        nombre=datos["nombre"],
        url_base=datos["url_base"],
        zona_horaria=datos.get("zona_horaria", "UTC"),
        verificar_certificado_tls=datos.get("verificar_certificado_tls", True),
        tiempo_espera_segundos=datos.get("tiempo_espera_segundos", 15),
    )
    db.session.add(entorno)
    registrar_auditoria("crear", "entorno", datos={"nombre": entorno.nombre})
    db.session.commit()
    return entorno


def crear_modulo(proyecto_id: UUID, datos: dict) -> ModuloObjetivo:
    modulo = ModuloObjetivo(
        proyecto_id=proyecto_id,
        nombre=datos["nombre"],
        descripcion=datos.get("descripcion", ""),
        critico=datos.get("critico", True),
    )
    db.session.add(modulo)
    registrar_auditoria("crear", "modulo_objetivo", datos={"nombre": modulo.nombre})
    db.session.commit()
    return modulo


def crear_secreto(proyecto_id: UUID, datos: dict, usuario_id: str | None) -> Secreto:
    Proyecto.query.get_or_404(proyecto_id)
    nombre = str(datos.get("nombre", "")).strip()
    valor = datos.get("valor")
    if not nombre:
        raise ConfiguracionInvalida("El nombre del secreto es obligatorio.")
    if valor is None or str(valor) == "":
        raise ConfiguracionInvalida("El valor del secreto es obligatorio.")

    entorno_id = datos.get("entorno_id")
    secreto = Secreto.query.filter_by(proyecto_id=proyecto_id, entorno_id=entorno_id, nombre=nombre).first()
    accion = "actualizar" if secreto else "crear"
    valor_cifrado = cifrar_valor(current_app.config["CLAVE_CIFRADO_SECRETOS"], str(valor))
    if secreto is None:
        secreto = Secreto(
            proyecto_id=proyecto_id,
            entorno_id=entorno_id,
            nombre=nombre,
            tipo=datos.get("tipo", "texto"),
            valor_cifrado=valor_cifrado,
            creado_por=UUID(usuario_id) if usuario_id else None,
        )
        db.session.add(secreto)
    else:
        secreto.tipo = datos.get("tipo", secreto.tipo)
        secreto.valor_cifrado = valor_cifrado

    registrar_auditoria(accion, "secreto", datos={"nombre": secreto.nombre, "tipo": secreto.tipo})
    db.session.commit()
    return secreto
