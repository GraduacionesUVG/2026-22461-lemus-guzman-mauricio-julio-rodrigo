import yaml
from datetime import datetime, timezone
from uuid import UUID

from aplicacion.extensiones import db
from aplicacion.modelos import CasoPrueba, Entorno, Monitor, Pipeline, Proyecto
from aplicacion.modelos import ModuloObjetivo, PasoCasoPrueba, PasoPipeline, Programacion
from aplicacion.servicios.validaciones import ConfiguracionInvalida, validar_pasos_caso, validar_url_web


def cargar_yaml_seguro(texto: str) -> dict:
    contenido = yaml.safe_load(texto) or {}
    if contenido.get("version") != 1:
        raise ConfiguracionInvalida("La version del esquema YAML debe ser 1.")
    return contenido


def validar_configuracion_yaml(texto: str) -> dict:
    contenido = cargar_yaml_seguro(texto)
    proyecto = contenido.get("proyecto") or {}
    if not proyecto.get("nombre"):
        raise ConfiguracionInvalida("El YAML requiere proyecto.nombre.")
    nombres_entornos = set()
    for entorno in contenido.get("entornos", []):
        if entorno["nombre"] in nombres_entornos:
            raise ConfiguracionInvalida("Existen entornos duplicados.")
        nombres_entornos.add(entorno["nombre"])
        validar_url_web(entorno["url_base"])
    nombres_casos = set()
    for caso in contenido.get("casos_prueba", []):
        if caso["nombre"] in nombres_casos:
            raise ConfiguracionInvalida("Existen casos de prueba duplicados.")
        nombres_casos.add(caso["nombre"])
        try:
            validar_pasos_caso(caso.get("pasos", []))
        except ConfiguracionInvalida as exc:
            if "Tipo de paso no permitido" in str(exc):
                raise ConfiguracionInvalida(str(exc).replace("Tipo de paso no permitido", "Tipo de paso YAML no permitido")) from exc
            raise
    nombres_monitores = set()
    for monitor in contenido.get("monitores", []):
        if monitor["nombre"] in nombres_monitores:
            raise ConfiguracionInvalida("Existen monitores duplicados.")
        nombres_monitores.add(monitor["nombre"])
    for pipeline in contenido.get("pipelines", []):
        for paso in pipeline.get("pasos", []):
            referencia = paso.get("referencia")
            if paso.get("tipo") == "monitor" and referencia not in nombres_monitores:
                raise ConfiguracionInvalida(f"El monitor referenciado no existe: {referencia}.")
            if paso.get("tipo") == "caso_prueba" and referencia not in nombres_casos:
                raise ConfiguracionInvalida(f"El caso de prueba referenciado no existe: {referencia}.")
    nombres_pipelines = {pipeline["nombre"] for pipeline in contenido.get("pipelines", [])}
    for programacion in contenido.get("programaciones", []):
        if programacion.get("pipeline") not in nombres_pipelines:
            raise ConfiguracionInvalida(f"El pipeline de la programacion no existe: {programacion.get('pipeline')}.")
    return {"valido": True, "resumen": {"entornos": len(contenido.get("entornos", [])), "casos_prueba": len(contenido.get("casos_prueba", [])), "monitores": len(contenido.get("monitores", [])), "pipelines": len(contenido.get("pipelines", []))}}


def _nombres(elementos: list[dict]) -> set[str]:
    return {elemento["nombre"] for elemento in elementos}


def _diferencia_nombres(importados: set[str], existentes: set[str]) -> dict:
    return {
        "nuevos": sorted(importados - existentes),
        "coincidentes": sorted(importados & existentes),
        "sin_cambios": sorted(existentes - importados),
    }


def previsualizar_importacion_yaml(texto: str) -> dict:
    validacion = validar_configuracion_yaml(texto)
    contenido = cargar_yaml_seguro(texto)
    proyecto_datos = contenido["proyecto"]
    proyecto_existente = Proyecto.query.filter_by(nombre=proyecto_datos["nombre"]).first()

    resumen = {
        **validacion["resumen"],
        "modulos_objetivo": len(contenido.get("modulos_objetivo", [])),
        "programaciones": len(contenido.get("programaciones", [])),
        "pasos_casos_prueba": sum(len(caso.get("pasos", [])) for caso in contenido.get("casos_prueba", [])),
        "pasos_pipelines": sum(len(pipeline.get("pasos", [])) for pipeline in contenido.get("pipelines", [])),
    }
    comparacion = {
        "proyecto": {
            "nombre": proyecto_datos["nombre"],
            "accion": "crear_nuevo",
            "id_existente": None,
        },
        "modulos_objetivo": _diferencia_nombres(_nombres(contenido.get("modulos_objetivo", [])), set()),
        "entornos": _diferencia_nombres(_nombres(contenido.get("entornos", [])), set()),
        "casos_prueba": _diferencia_nombres(_nombres(contenido.get("casos_prueba", [])), set()),
        "monitores": _diferencia_nombres(_nombres(contenido.get("monitores", [])), set()),
        "pipelines": _diferencia_nombres(_nombres(contenido.get("pipelines", [])), set()),
        "programaciones": _diferencia_nombres(_nombres(contenido.get("programaciones", [])), set()),
    }
    advertencias = []

    if proyecto_existente:
        comparacion["proyecto"] = {
            "nombre": proyecto_existente.nombre,
            "accion": "crear_copia",
            "id_existente": str(proyecto_existente.id),
        }
        comparacion["modulos_objetivo"] = _diferencia_nombres(
            _nombres(contenido.get("modulos_objetivo", [])),
            {modulo.nombre for modulo in ModuloObjetivo.query.filter_by(proyecto_id=proyecto_existente.id).all()},
        )
        comparacion["entornos"] = _diferencia_nombres(
            _nombres(contenido.get("entornos", [])),
            {entorno.nombre for entorno in Entorno.query.filter_by(proyecto_id=proyecto_existente.id).all()},
        )
        comparacion["casos_prueba"] = _diferencia_nombres(
            _nombres(contenido.get("casos_prueba", [])),
            {caso.nombre for caso in CasoPrueba.query.filter_by(proyecto_id=proyecto_existente.id).all()},
        )
        comparacion["monitores"] = _diferencia_nombres(
            _nombres(contenido.get("monitores", [])),
            {monitor.nombre for monitor in Monitor.query.filter_by(proyecto_id=proyecto_existente.id).all()},
        )
        comparacion["pipelines"] = _diferencia_nombres(
            _nombres(contenido.get("pipelines", [])),
            {pipeline.nombre for pipeline in Pipeline.query.filter_by(proyecto_id=proyecto_existente.id).all()},
        )
        programaciones_existentes = (
            Programacion.query
            .join(Pipeline, Programacion.pipeline_id == Pipeline.id)
            .filter(Pipeline.proyecto_id == proyecto_existente.id)
            .all()
        )
        comparacion["programaciones"] = _diferencia_nombres(
            _nombres(contenido.get("programaciones", [])),
            {programacion.nombre for programacion in programaciones_existentes},
        )
        advertencias.append("Ya existe un proyecto con este nombre; la importacion actual creara un proyecto nuevo con datos duplicados.")

    if contenido.get("monitores") and not contenido.get("entornos"):
        advertencias.append("Los monitores se importaran sin entorno asociado porque el YAML no define entornos.")
    if contenido.get("casos_prueba") and not contenido.get("modulos_objetivo"):
        advertencias.append("Los casos se importaran sin modulo objetivo porque el YAML no define modulos.")

    return {
        "valido": True,
        "proyecto": {
            "nombre": proyecto_datos["nombre"],
            "descripcion": proyecto_datos.get("descripcion", ""),
            "tecnologia_referencial": proyecto_datos.get("tecnologia_referencial"),
            "responsable": proyecto_datos.get("responsable"),
        },
        "resumen": resumen,
        "comparacion": comparacion,
        "advertencias": advertencias,
    }


def importar_configuracion_yaml(texto: str, usuario_id: str | None) -> dict:
    validar_configuracion_yaml(texto)
    contenido = cargar_yaml_seguro(texto)
    identidad = UUID(usuario_id) if usuario_id else None
    proyecto_datos = contenido["proyecto"]
    proyecto = Proyecto(
        nombre=proyecto_datos["nombre"],
        descripcion=proyecto_datos.get("descripcion", ""),
        tecnologia_referencial=proyecto_datos.get("tecnologia_referencial"),
        responsable=proyecto_datos.get("responsable"),
        creado_por=identidad,
    )
    db.session.add(proyecto)
    db.session.flush()
    modulos_por_nombre = {}
    for modulo_datos in contenido.get("modulos_objetivo", []):
        modulo = ModuloObjetivo(
            proyecto_id=proyecto.id,
            nombre=modulo_datos["nombre"],
            descripcion=modulo_datos.get("descripcion", ""),
            critico=modulo_datos.get("critico", True),
        )
        db.session.add(modulo)
        modulos_por_nombre[modulo.nombre] = modulo
    entornos_creados = []
    for entorno_datos in contenido.get("entornos", []):
        entorno = Entorno(
            proyecto_id=proyecto.id,
            nombre=entorno_datos["nombre"],
            url_base=entorno_datos["url_base"],
            zona_horaria=entorno_datos.get("zona_horaria", "UTC"),
            verificar_certificado_tls=entorno_datos.get("verificar_certificado_tls", True),
            tiempo_espera_segundos=entorno_datos.get("tiempo_espera_segundos", 15),
        )
        db.session.add(entorno)
        entornos_creados.append(entorno)
    db.session.flush()
    casos_por_nombre = {}
    for caso_datos in contenido.get("casos_prueba", []):
        modulo = modulos_por_nombre.get(caso_datos.get("modulo_objetivo"))
        caso = CasoPrueba(
            proyecto_id=proyecto.id,
            modulo_objetivo_id=modulo.id if modulo else None,
            nombre=caso_datos["nombre"],
            descripcion=caso_datos.get("descripcion", ""),
            prioridad=caso_datos.get("prioridad", "media"),
            requiere_revision_humana=caso_datos.get("requiere_revision_humana", False),
            creado_por=identidad,
        )
        db.session.add(caso)
        db.session.flush()
        for paso_datos in caso_datos.get("pasos", []):
            db.session.add(PasoCasoPrueba(
                caso_prueba_id=caso.id,
                orden=paso_datos["orden"],
                tipo=paso_datos["tipo"],
                nombre=paso_datos["nombre"],
                configuracion=paso_datos.get("configuracion", {}),
                continuar_si_falla=paso_datos.get("continuar_si_falla", False),
                capturar_evidencia=paso_datos.get("capturar_evidencia", True),
            ))
        casos_por_nombre[caso.nombre] = caso
    monitores_por_nombre = {}
    entorno_base = entornos_creados[0] if entornos_creados else None
    for monitor_datos in contenido.get("monitores", []):
        monitor = Monitor(
            proyecto_id=proyecto.id,
            entorno_id=entorno_base.id if entorno_base else None,
            nombre=monitor_datos["nombre"],
            tipo=monitor_datos["tipo"],
            configuracion=monitor_datos.get("configuracion", {}),
            intervalo_recomendado_segundos=monitor_datos.get("intervalo_recomendado_segundos", 300),
        )
        db.session.add(monitor)
        monitores_por_nombre[monitor.nombre] = monitor
    db.session.flush()
    pipelines_por_nombre = {}
    for pipeline_datos in contenido.get("pipelines", []):
        pipeline = Pipeline(
            proyecto_id=proyecto.id,
            nombre=pipeline_datos["nombre"],
            descripcion=pipeline_datos.get("descripcion", ""),
            detener_ante_fallo=pipeline_datos.get("detener_ante_fallo", True),
            creado_por=identidad,
        )
        db.session.add(pipeline)
        db.session.flush()
        for paso_datos in pipeline_datos.get("pasos", []):
            monitor = monitores_por_nombre.get(paso_datos.get("referencia"))
            caso = casos_por_nombre.get(paso_datos.get("referencia"))
            db.session.add(PasoPipeline(
                pipeline_id=pipeline.id,
                orden=paso_datos["orden"],
                tipo=paso_datos["tipo"],
                monitor_id=monitor.id if monitor else None,
                caso_prueba_id=caso.id if caso else None,
                nombre=paso_datos.get("nombre") or paso_datos.get("referencia"),
                continuar_si_falla=paso_datos.get("continuar_si_falla", False),
                configuracion=paso_datos.get("configuracion", {}),
            ))
        pipelines_por_nombre[pipeline.nombre] = pipeline
    for programacion_datos in contenido.get("programaciones", []):
        pipeline = pipelines_por_nombre.get(programacion_datos["pipeline"])
        frecuencia = programacion_datos.get("frecuencia", {})
        db.session.add(Programacion(
            pipeline_id=pipeline.id,
            nombre=programacion_datos["nombre"],
            tipo_frecuencia=frecuencia.get("tipo", "diaria"),
            configuracion_frecuencia=frecuencia,
            zona_horaria=programacion_datos.get("zona_horaria", "UTC"),
            siguiente_ejecucion=datetime.now(timezone.utc),
        ))
    db.session.commit()
    return {"aplicado": True, "proyecto_id": str(proyecto.id), "resumen": validar_configuracion_yaml(texto)["resumen"]}


def exportar_proyecto_yaml(proyecto: Proyecto) -> str:
    entornos = Entorno.query.filter_by(proyecto_id=proyecto.id).all()
    casos = CasoPrueba.query.filter_by(proyecto_id=proyecto.id).all()
    monitores = Monitor.query.filter_by(proyecto_id=proyecto.id).all()
    pipelines = Pipeline.query.filter_by(proyecto_id=proyecto.id).all()
    casos_por_id = {caso.id: caso.nombre for caso in casos}
    monitores_por_id = {monitor.id: monitor.nombre for monitor in monitores}
    contenido = {
        "version": 1,
        "proyecto": {
            "nombre": proyecto.nombre,
            "descripcion": proyecto.descripcion,
            "tecnologia_referencial": proyecto.tecnologia_referencial,
        },
        "entornos": [
            {
                "nombre": entorno.nombre,
                "url_base": entorno.url_base,
                "zona_horaria": entorno.zona_horaria,
                "verificar_certificado_tls": entorno.verificar_certificado_tls,
                "tiempo_espera_segundos": entorno.tiempo_espera_segundos,
            }
            for entorno in entornos
        ],
        "casos_prueba": [
            {
                "nombre": caso.nombre,
                "prioridad": caso.prioridad,
                "requiere_revision_humana": caso.requiere_revision_humana,
                "pasos": [
                    {
                        "orden": paso.orden,
                        "tipo": paso.tipo,
                        "nombre": paso.nombre,
                        "configuracion": paso.configuracion,
                    }
                    for paso in caso.pasos
                ],
            }
            for caso in casos
        ],
        "monitores": [
            {
                "nombre": monitor.nombre,
                "tipo": monitor.tipo,
                "configuracion": monitor.configuracion,
            }
            for monitor in monitores
        ],
        "pipelines": [
            {
                "nombre": pipeline.nombre,
                "detener_ante_fallo": pipeline.detener_ante_fallo,
                "pasos": [
                    {
                        "orden": paso.orden,
                        "tipo": paso.tipo,
                        "nombre": paso.nombre,
                        "referencia": monitores_por_id.get(paso.monitor_id) if paso.tipo == "monitor" else casos_por_id.get(paso.caso_prueba_id),
                    }
                    for paso in pipeline.pasos
                ],
            }
            for pipeline in pipelines
        ],
    }
    return yaml.safe_dump(contenido, allow_unicode=True, sort_keys=False)
