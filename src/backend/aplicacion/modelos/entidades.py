import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from aplicacion.extensiones import db
from aplicacion.utilidades.tiempo import ahora_utc


def crear_uuid() -> uuid.UUID:
    return uuid.uuid4()


tipo_json = JSON().with_variant(JSONB, "postgresql")


class MezclaFechas:
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc, nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc, onupdate=ahora_utc, nullable=False)


class Usuario(db.Model, MezclaFechas):
    __tablename__ = "usuarios"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    correo: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    contrasena_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tour_completado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    roles: Mapped[list["Rol"]] = relationship(secondary="usuarios_roles", back_populates="usuarios")


class Rol(db.Model):
    __tablename__ = "roles"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    nombre: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False)
    usuarios: Mapped[list[Usuario]] = relationship(secondary="usuarios_roles", back_populates="roles")


class UsuarioRol(db.Model):
    __tablename__ = "usuarios_roles"
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("usuarios.id"), primary_key=True)
    rol_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("roles.id"), primary_key=True)


class Proyecto(db.Model, MezclaFechas):
    __tablename__ = "proyectos"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    nombre: Mapped[str] = mapped_column(String(180), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tecnologia_referencial: Mapped[str | None] = mapped_column(String(120))
    responsable: Mapped[str | None] = mapped_column(String(160))
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    creado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("usuarios.id"))
    entornos: Mapped[list["Entorno"]] = relationship(back_populates="proyecto")


class ModuloObjetivo(db.Model):
    __tablename__ = "modulos_objetivo"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    proyecto_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("proyectos.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, default="", nullable=False)
    critico: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (UniqueConstraint("proyecto_id", "nombre", name="uq_modulo_proyecto_nombre"),)


class Entorno(db.Model):
    __tablename__ = "entornos"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    proyecto_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("proyectos.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    url_base: Mapped[str] = mapped_column(String(500), nullable=False)
    zona_horaria: Mapped[str] = mapped_column(String(80), default="UTC", nullable=False)
    verificar_certificado_tls: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tiempo_espera_segundos: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    proyecto: Mapped[Proyecto] = relationship(back_populates="entornos")
    __table_args__ = (UniqueConstraint("proyecto_id", "nombre", name="uq_entorno_proyecto_nombre"),)


class Secreto(db.Model, MezclaFechas):
    __tablename__ = "secretos"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    proyecto_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("proyectos.id"), nullable=False, index=True)
    entorno_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("entornos.id"))
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo: Mapped[str] = mapped_column(String(60), nullable=False)
    valor_cifrado: Mapped[str] = mapped_column(Text, nullable=False)
    creado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("usuarios.id"))
    __table_args__ = (UniqueConstraint("proyecto_id", "entorno_id", "nombre", name="uq_secreto_alcance_nombre"),)


class CasoPrueba(db.Model, MezclaFechas):
    __tablename__ = "casos_prueba"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    proyecto_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("proyectos.id"), nullable=False, index=True)
    modulo_objetivo_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("modulos_objetivo.id"))
    nombre: Mapped[str] = mapped_column(String(180), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, default="", nullable=False)
    prioridad: Mapped[str] = mapped_column(String(30), default="media", nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requiere_revision_humana: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    creado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("usuarios.id"))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    pasos: Mapped[list["PasoCasoPrueba"]] = relationship(back_populates="caso_prueba", cascade="all, delete-orphan", order_by="PasoCasoPrueba.orden")


class PasoCasoPrueba(db.Model):
    __tablename__ = "pasos_caso_prueba"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    caso_prueba_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("casos_prueba.id"), nullable=False, index=True)
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[str] = mapped_column(String(80), nullable=False)
    nombre: Mapped[str] = mapped_column(String(180), nullable=False)
    configuracion: Mapped[dict] = mapped_column(tipo_json, default=dict, nullable=False)
    continuar_si_falla: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    capturar_evidencia: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    caso_prueba: Mapped[CasoPrueba] = relationship(back_populates="pasos")


class Monitor(db.Model):
    __tablename__ = "monitores"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    proyecto_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("proyectos.id"), nullable=False, index=True)
    entorno_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("entornos.id"))
    nombre: Mapped[str] = mapped_column(String(180), nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    configuracion: Mapped[dict] = mapped_column(tipo_json, default=dict, nullable=False)
    intervalo_recomendado_segundos: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Pipeline(db.Model, MezclaFechas):
    __tablename__ = "pipelines"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    proyecto_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("proyectos.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(180), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, default="", nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    detener_ante_fallo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    creado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("usuarios.id"))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    pasos: Mapped[list["PasoPipeline"]] = relationship(back_populates="pipeline", cascade="all, delete-orphan", order_by="PasoPipeline.orden")


class PasoPipeline(db.Model):
    __tablename__ = "pasos_pipeline"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("pipelines.id"), nullable=False, index=True)
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[str] = mapped_column(String(60), nullable=False)
    caso_prueba_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("casos_prueba.id"))
    monitor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("monitores.id"))
    nombre: Mapped[str] = mapped_column(String(180), nullable=False)
    continuar_si_falla: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    configuracion: Mapped[dict] = mapped_column(tipo_json, default=dict, nullable=False)
    pipeline: Mapped[Pipeline] = relationship(back_populates="pasos")


class Programacion(db.Model):
    __tablename__ = "programaciones"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("pipelines.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(180), nullable=False)
    tipo_frecuencia: Mapped[str] = mapped_column(String(60), nullable=False)
    configuracion_frecuencia: Mapped[dict] = mapped_column(tipo_json, default=dict, nullable=False)
    zona_horaria: Mapped[str] = mapped_column(String(80), default="UTC", nullable=False)
    siguiente_ejecucion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Ejecucion(db.Model):
    __tablename__ = "ejecuciones"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("pipelines.id"), nullable=False, index=True)
    entorno_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("entornos.id"), nullable=False, index=True)
    origen: Mapped[str] = mapped_column(String(60), nullable=False)
    estado: Mapped[str] = mapped_column(String(60), default="en_cola", nullable=False, index=True)
    fecha_encolado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc, nullable=False)
    fecha_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_deteccion_primer_fallo: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duracion_milisegundos: Mapped[int | None] = mapped_column(Integer)
    error_tecnico: Mapped[str | None] = mapped_column(Text)
    trabajador_id: Mapped[str | None] = mapped_column(String(120))
    creado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("usuarios.id"))
    pipeline: Mapped["Pipeline"] = relationship()
    entorno: Mapped["Entorno"] = relationship()
    resultados: Mapped[list["ResultadoPaso"]] = relationship(back_populates="ejecucion", cascade="all, delete-orphan")


class InformeEjecucion(db.Model):
    __tablename__ = "informes_ejecucion"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    ejecucion_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("ejecuciones.id"), nullable=False, index=True)
    ruta_relativa: Mapped[str] = mapped_column(String(500), nullable=False)
    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo_contenido: Mapped[str] = mapped_column(String(120), default="application/pdf", nullable=False)
    tamano_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    generado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc, nullable=False)
    zona_horaria: Mapped[str] = mapped_column(String(80), default="America/Guatemala", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    ejecucion: Mapped[Ejecucion] = relationship()


class ResultadoPaso(db.Model):
    __tablename__ = "resultados_paso"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    ejecucion_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("ejecuciones.id"), nullable=False, index=True)
    paso_pipeline_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("pasos_pipeline.id"))
    paso_caso_prueba_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("pasos_caso_prueba.id"))
    tipo: Mapped[str] = mapped_column(String(60), nullable=False)
    estado: Mapped[str] = mapped_column(String(60), nullable=False)
    esperado: Mapped[str] = mapped_column(Text, default="", nullable=False)
    obtenido: Mapped[str] = mapped_column(Text, default="", nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, default="", nullable=False)
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc, nullable=False)
    fecha_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duracion_milisegundos: Mapped[int | None] = mapped_column(Integer)
    datos_tecnicos_sanitizados: Mapped[dict] = mapped_column(tipo_json, default=dict, nullable=False)
    ejecucion: Mapped[Ejecucion] = relationship(back_populates="resultados")


class RevisionEjecucion(db.Model, MezclaFechas):
    __tablename__ = "revisiones_ejecucion"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    ejecucion_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("ejecuciones.id"), nullable=False, index=True)
    clasificacion: Mapped[str] = mapped_column(String(60), nullable=False)
    comentario: Mapped[str] = mapped_column(Text, default="", nullable=False)
    revisado_por: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)


class RevisionPaso(db.Model, MezclaFechas):
    __tablename__ = "revisiones_paso"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    resultado_paso_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("resultados_paso.id"), nullable=False, index=True)
    clasificacion: Mapped[str] = mapped_column(String(60), nullable=False)
    comentario: Mapped[str] = mapped_column(Text, default="", nullable=False)
    revisado_por: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)


class Evidencia(db.Model):
    __tablename__ = "evidencias"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    ejecucion_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("ejecuciones.id"), nullable=False, index=True)
    resultado_paso_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("resultados_paso.id"))
    tipo: Mapped[str] = mapped_column(String(80), nullable=False)
    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    ruta_relativa: Mapped[str] = mapped_column(String(500), nullable=False)
    tipo_contenido: Mapped[str] = mapped_column(String(120), nullable=False)
    tamano_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc, nullable=False)


class CanalNotificacion(db.Model):
    __tablename__ = "canales_notificacion"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    proyecto_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("proyectos.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(180), nullable=False)
    tipo: Mapped[str] = mapped_column(String(60), nullable=False)
    configuracion_cifrada: Mapped[str] = mapped_column(Text, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Notificacion(db.Model):
    __tablename__ = "notificaciones"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    ejecucion_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("ejecuciones.id"), nullable=False, index=True)
    canal_notificacion_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("canales_notificacion.id"))
    estado: Mapped[str] = mapped_column(String(60), nullable=False)
    fecha_solicitud: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc, nullable=False)
    fecha_envio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    intentos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_sanitizado: Mapped[str] = mapped_column(Text, default="", nullable=False)


class Alerta(db.Model):
    __tablename__ = "alertas"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    ejecucion_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("ejecuciones.id"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(80), nullable=False)
    severidad: Mapped[str] = mapped_column(String(60), nullable=False)
    estado_revision: Mapped[str] = mapped_column(String(60), default="pendiente", nullable=False)
    fecha_deteccion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc, nullable=False)
    fecha_reconocimiento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reconocida_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("usuarios.id"))
    clasificacion_manual: Mapped[str] = mapped_column(String(60), default="pendiente", nullable=False)
    observacion_revision: Mapped[str] = mapped_column(Text, default="", nullable=False)


class Auditoria(db.Model):
    __tablename__ = "auditorias"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("usuarios.id"))
    accion: Mapped[str] = mapped_column(String(120), nullable=False)
    entidad: Mapped[str] = mapped_column(String(120), nullable=False)
    entidad_id: Mapped[str | None] = mapped_column(String(120))
    datos_sanitizados: Mapped[dict] = mapped_column(tipo_json, default=dict, nullable=False)
    direccion_ip: Mapped[str | None] = mapped_column(String(80))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc, nullable=False)


class MedicionEvaluacion(db.Model):
    __tablename__ = "mediciones_evaluacion"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=crear_uuid)
    proyecto_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("proyectos.id"), nullable=False, index=True)
    escenario: Mapped[str] = mapped_column(String(180), nullable=False)
    enfoque: Mapped[str] = mapped_column(String(60), nullable=False)
    fallos_esperados: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fallos_detectados: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tiempo_deteccion_milisegundos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tiempo_notificacion_milisegundos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tiempo_consulta_milisegundos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resultados_almacenados: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evidencias_generadas: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    observaciones: Mapped[str] = mapped_column(Text, default="", nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc, nullable=False)
