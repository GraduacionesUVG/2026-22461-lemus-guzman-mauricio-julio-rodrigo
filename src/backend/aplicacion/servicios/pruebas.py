from uuid import UUID

from flask_jwt_extended import get_jwt_identity

from aplicacion.auditoria.servicio import registrar_auditoria
from aplicacion.extensiones import db
from aplicacion.modelos import CasoPrueba, Monitor, PasoCasoPrueba
from aplicacion.servicios.validaciones import validar_pasos_caso


def crear_caso_prueba(datos: dict) -> CasoPrueba:
    pasos = datos.get("pasos", [])
    validar_pasos_caso(pasos, datos["proyecto_id"])
    caso = CasoPrueba(
        proyecto_id=UUID(datos["proyecto_id"]),
        modulo_objetivo_id=UUID(datos["modulo_objetivo_id"]) if datos.get("modulo_objetivo_id") else None,
        nombre=datos["nombre"],
        descripcion=datos.get("descripcion", ""),
        prioridad=datos.get("prioridad", "media"),
        requiere_revision_humana=datos.get("requiere_revision_humana", False),
        creado_por=UUID(get_jwt_identity()),
    )
    db.session.add(caso)
    db.session.flush()
    for paso in pasos:
        db.session.add(PasoCasoPrueba(
            caso_prueba_id=caso.id,
            orden=paso["orden"],
            tipo=paso["tipo"],
            nombre=paso["nombre"],
            configuracion=paso.get("configuracion", {}),
            continuar_si_falla=paso.get("continuar_si_falla", False),
            capturar_evidencia=paso.get("capturar_evidencia", True),
        ))
    registrar_auditoria("crear", "caso_prueba", datos={"nombre": caso.nombre})
    db.session.commit()
    return caso


def actualizar_caso_prueba(caso_id: UUID, datos: dict) -> CasoPrueba:
    caso = CasoPrueba.query.get_or_404(caso_id)
    for campo in ["nombre", "descripcion", "prioridad", "activo", "modulo_objetivo_id", "requiere_revision_humana"]:
        if campo in datos:
            setattr(caso, campo, datos[campo])
    if "pasos" in datos:
        validar_pasos_caso(datos["pasos"], caso.proyecto_id)
        caso.pasos.clear()
        db.session.flush()
        for paso in datos["pasos"]:
            caso.pasos.append(PasoCasoPrueba(
                orden=paso["orden"],
                tipo=paso["tipo"],
                nombre=paso["nombre"],
                configuracion=paso.get("configuracion", {}),
                continuar_si_falla=paso.get("continuar_si_falla", False),
                capturar_evidencia=paso.get("capturar_evidencia", True),
            ))
        caso.version += 1
    registrar_auditoria("actualizar", "caso_prueba", str(caso.id), datos)
    db.session.commit()
    return caso


def crear_monitor(datos: dict) -> Monitor:
    monitor = Monitor(
        proyecto_id=UUID(datos["proyecto_id"]),
        entorno_id=UUID(datos["entorno_id"]) if datos.get("entorno_id") else None,
        nombre=datos["nombre"],
        tipo=datos["tipo"],
        configuracion=datos.get("configuracion", {}),
        intervalo_recomendado_segundos=datos.get("intervalo_recomendado_segundos", 300),
        activo=datos.get("activo", True),
    )
    db.session.add(monitor)
    registrar_auditoria("crear", "monitor", datos={"nombre": monitor.nombre, "tipo": monitor.tipo})
    db.session.commit()
    return monitor
