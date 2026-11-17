from datetime import datetime, timedelta, timezone
from uuid import UUID

from flask_jwt_extended import get_jwt_identity

from aplicacion.auditoria.servicio import registrar_auditoria
from aplicacion.extensiones import db
from aplicacion.modelos import Ejecucion, PasoPipeline, Pipeline, Programacion
from aplicacion.servicios.validaciones import ConfiguracionInvalida
from aplicacion.utilidades.tiempo import asegurar_utc, ahora_utc, obtener_zona_horaria


def crear_pipeline(datos: dict) -> Pipeline:
    identidad = get_jwt_identity()
    pipeline = Pipeline(
        proyecto_id=UUID(datos["proyecto_id"]),
        nombre=datos["nombre"],
        descripcion=datos.get("descripcion", ""),
        detener_ante_fallo=datos.get("detener_ante_fallo", True),
        creado_por=UUID(identidad) if identidad else None,
    )
    db.session.add(pipeline)
    db.session.flush()
    for paso in datos.get("pasos", []):
        pipeline.pasos.append(PasoPipeline(
            orden=paso["orden"],
            tipo=paso["tipo"],
            caso_prueba_id=UUID(paso["caso_prueba_id"]) if paso.get("caso_prueba_id") else None,
            monitor_id=UUID(paso["monitor_id"]) if paso.get("monitor_id") else None,
            nombre=paso["nombre"],
            continuar_si_falla=paso.get("continuar_si_falla", False),
            configuracion=paso.get("configuracion", {}),
        ))
    registrar_auditoria("crear", "pipeline", datos={"nombre": pipeline.nombre})
    db.session.commit()
    return pipeline


def actualizar_pipeline(pipeline_id: UUID, datos: dict) -> Pipeline:
    pipeline = Pipeline.query.get_or_404(pipeline_id)
    for campo in ["nombre", "descripcion", "activo", "detener_ante_fallo"]:
        if campo in datos:
            setattr(pipeline, campo, datos[campo])
    if "pasos" in datos:
        pipeline.pasos.clear()
        db.session.flush()
        for paso in datos["pasos"]:
            pipeline.pasos.append(PasoPipeline(
                orden=paso["orden"],
                tipo=paso["tipo"],
                caso_prueba_id=UUID(paso["caso_prueba_id"]) if paso.get("caso_prueba_id") else None,
                monitor_id=UUID(paso["monitor_id"]) if paso.get("monitor_id") else None,
                nombre=paso["nombre"],
                continuar_si_falla=paso.get("continuar_si_falla", False),
                configuracion=paso.get("configuracion", {}),
            ))
        pipeline.version += 1
    registrar_auditoria("actualizar", "pipeline", str(pipeline.id), datos)
    db.session.commit()
    return pipeline


def encolar_ejecucion(pipeline_id: UUID, entorno_id: UUID, origen: str = "manual") -> Ejecucion:
    try:
        identidad = get_jwt_identity()
    except RuntimeError:
        identidad = None
    ejecucion = Ejecucion(
        pipeline_id=UUID(str(pipeline_id)),
        entorno_id=UUID(str(entorno_id)),
        origen=origen,
        estado="en_cola",
        creado_por=UUID(identidad) if identidad else None,
    )
    db.session.add(ejecucion)
    registrar_auditoria("encolar", "ejecucion", datos={"pipeline_id": str(pipeline_id), "entorno_id": str(entorno_id)})
    db.session.commit()
    return ejecucion


def convertir_fecha(valor) -> datetime:
    if isinstance(valor, datetime):
        return asegurar_utc(valor) or ahora_utc()
    if isinstance(valor, str):
        return asegurar_utc(datetime.fromisoformat(valor.replace("Z", "+00:00"))) or ahora_utc()
    return ahora_utc()


def validar_configuracion_programacion(tipo_frecuencia: str, configuracion: dict) -> None:
    if tipo_frecuencia not in {"minutos", "horas", "diaria"}:
        raise ConfiguracionInvalida("La frecuencia debe ser minutos, horas o diaria.")
    if not configuracion.get("entorno_id"):
        raise ConfiguracionInvalida("La programacion requiere un entorno.")
    if tipo_frecuencia in {"minutos", "horas"}:
        cada = int(configuracion.get("cada", 0))
        if cada < 1:
            raise ConfiguracionInvalida("El intervalo debe ser mayor a cero.")
    if tipo_frecuencia == "diaria":
        hora = configuracion.get("hora", "06:00")
        partes = hora.split(":")
        if len(partes) != 2 or not all(parte.isdigit() for parte in partes):
            raise ConfiguracionInvalida("La hora diaria debe usar formato HH:MM.")
        horas, minutos = int(partes[0]), int(partes[1])
        if horas > 23 or minutos > 59:
            raise ConfiguracionInvalida("La hora diaria no es valida.")


def calcular_siguiente_programacion(tipo_frecuencia: str, configuracion: dict, base: datetime | None = None, zona_horaria: str = "UTC") -> datetime:
    validar_configuracion_programacion(tipo_frecuencia, configuracion)
    referencia = asegurar_utc(base) or ahora_utc()
    if tipo_frecuencia == "minutos":
        return referencia + timedelta(minutes=int(configuracion.get("cada", 15)))
    if tipo_frecuencia == "horas":
        return referencia + timedelta(hours=int(configuracion.get("cada", 1)))
    zona = obtener_zona_horaria(zona_horaria)
    referencia_local = referencia.astimezone(zona)
    hora = configuracion.get("hora", "06:00")
    horas, minutos = [int(parte) for parte in hora.split(":")]
    siguiente = referencia_local.replace(hour=horas, minute=minutos, second=0, microsecond=0)
    if siguiente <= referencia_local:
        siguiente = siguiente + timedelta(days=1)
    return siguiente.astimezone(timezone.utc)


def crear_programacion(datos: dict) -> Programacion:
    configuracion = datos.get("configuracion_frecuencia", {})
    validar_configuracion_programacion(datos["tipo_frecuencia"], configuracion)
    zona_horaria = datos.get("zona_horaria", "UTC")
    siguiente = datos.get("siguiente_ejecucion")
    siguiente = convertir_fecha(siguiente) if siguiente else calcular_siguiente_programacion(datos["tipo_frecuencia"], configuracion, zona_horaria=zona_horaria)
    programacion = Programacion(
        pipeline_id=UUID(datos["pipeline_id"]),
        nombre=datos["nombre"],
        tipo_frecuencia=datos["tipo_frecuencia"],
        configuracion_frecuencia=configuracion,
        zona_horaria=zona_horaria,
        siguiente_ejecucion=siguiente,
        activo=datos.get("activo", True),
    )
    db.session.add(programacion)
    registrar_auditoria("crear", "programacion", datos={"nombre": programacion.nombre})
    db.session.commit()
    return programacion


def actualizar_programacion(programacion_id: UUID, datos: dict) -> Programacion:
    programacion = Programacion.query.get_or_404(programacion_id)
    tipo_frecuencia = datos.get("tipo_frecuencia", programacion.tipo_frecuencia)
    configuracion = datos.get("configuracion_frecuencia", programacion.configuracion_frecuencia)
    validar_configuracion_programacion(tipo_frecuencia, configuracion)
    for campo in ["nombre", "zona_horaria", "activo"]:
        if campo in datos:
            setattr(programacion, campo, datos[campo])
    programacion.tipo_frecuencia = tipo_frecuencia
    programacion.configuracion_frecuencia = configuracion
    if "siguiente_ejecucion" in datos:
        programacion.siguiente_ejecucion = convertir_fecha(datos["siguiente_ejecucion"])
    elif any(campo in datos for campo in {"tipo_frecuencia", "configuracion_frecuencia", "activo"}):
        programacion.siguiente_ejecucion = calcular_siguiente_programacion(tipo_frecuencia, configuracion, zona_horaria=programacion.zona_horaria)
    registrar_auditoria("actualizar", "programacion", str(programacion.id), {"nombre": programacion.nombre, "activo": programacion.activo})
    db.session.commit()
    return programacion
