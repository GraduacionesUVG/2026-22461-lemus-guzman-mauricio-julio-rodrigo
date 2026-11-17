from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '21c381edea85'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('roles',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('nombre', sa.String(length=80), nullable=False),
    sa.Column('descripcion', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('nombre')
    )
    op.create_table('usuarios',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('nombre', sa.String(length=160), nullable=False),
    sa.Column('correo', sa.String(length=255), nullable=False),
    sa.Column('contrasena_hash', sa.String(length=255), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('ultimo_acceso', sa.DateTime(timezone=True), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    sa.Column('actualizado_en', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_usuarios_correo'), ['correo'], unique=True)

    op.create_table('auditorias',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('usuario_id', sa.Uuid(), nullable=True),
    sa.Column('accion', sa.String(length=120), nullable=False),
    sa.Column('entidad', sa.String(length=120), nullable=False),
    sa.Column('entidad_id', sa.String(length=120), nullable=True),
    sa.Column('datos_sanitizados', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
    sa.Column('direccion_ip', sa.String(length=80), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('proyectos',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('nombre', sa.String(length=180), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=False),
    sa.Column('tecnologia_referencial', sa.String(length=120), nullable=True),
    sa.Column('responsable', sa.String(length=160), nullable=True),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('creado_por', sa.Uuid(), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    sa.Column('actualizado_en', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['creado_por'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('usuarios_roles',
    sa.Column('usuario_id', sa.Uuid(), nullable=False),
    sa.Column('rol_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['rol_id'], ['roles.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('usuario_id', 'rol_id')
    )
    op.create_table('canales_notificacion',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('proyecto_id', sa.Uuid(), nullable=False),
    sa.Column('nombre', sa.String(length=180), nullable=False),
    sa.Column('tipo', sa.String(length=60), nullable=False),
    sa.Column('configuracion_cifrada', sa.Text(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['proyecto_id'], ['proyectos.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('canales_notificacion', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_canales_notificacion_proyecto_id'), ['proyecto_id'], unique=False)

    op.create_table('entornos',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('proyecto_id', sa.Uuid(), nullable=False),
    sa.Column('nombre', sa.String(length=120), nullable=False),
    sa.Column('url_base', sa.String(length=500), nullable=False),
    sa.Column('zona_horaria', sa.String(length=80), nullable=False),
    sa.Column('verificar_certificado_tls', sa.Boolean(), nullable=False),
    sa.Column('tiempo_espera_segundos', sa.Integer(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['proyecto_id'], ['proyectos.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('proyecto_id', 'nombre', name='uq_entorno_proyecto_nombre')
    )
    with op.batch_alter_table('entornos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_entornos_proyecto_id'), ['proyecto_id'], unique=False)

    op.create_table('mediciones_evaluacion',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('proyecto_id', sa.Uuid(), nullable=False),
    sa.Column('escenario', sa.String(length=180), nullable=False),
    sa.Column('enfoque', sa.String(length=60), nullable=False),
    sa.Column('fallos_esperados', sa.Integer(), nullable=False),
    sa.Column('fallos_detectados', sa.Integer(), nullable=False),
    sa.Column('tiempo_deteccion_milisegundos', sa.Integer(), nullable=False),
    sa.Column('tiempo_notificacion_milisegundos', sa.Integer(), nullable=False),
    sa.Column('tiempo_consulta_milisegundos', sa.Integer(), nullable=False),
    sa.Column('resultados_almacenados', sa.Integer(), nullable=False),
    sa.Column('evidencias_generadas', sa.Integer(), nullable=False),
    sa.Column('observaciones', sa.Text(), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['proyecto_id'], ['proyectos.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('mediciones_evaluacion', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_mediciones_evaluacion_proyecto_id'), ['proyecto_id'], unique=False)

    op.create_table('modulos_objetivo',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('proyecto_id', sa.Uuid(), nullable=False),
    sa.Column('nombre', sa.String(length=160), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=False),
    sa.Column('critico', sa.Boolean(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['proyecto_id'], ['proyectos.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('proyecto_id', 'nombre', name='uq_modulo_proyecto_nombre')
    )
    with op.batch_alter_table('modulos_objetivo', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_modulos_objetivo_proyecto_id'), ['proyecto_id'], unique=False)

    op.create_table('pipelines',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('proyecto_id', sa.Uuid(), nullable=False),
    sa.Column('nombre', sa.String(length=180), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('detener_ante_fallo', sa.Boolean(), nullable=False),
    sa.Column('creado_por', sa.Uuid(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    sa.Column('actualizado_en', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['creado_por'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['proyecto_id'], ['proyectos.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('pipelines', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pipelines_proyecto_id'), ['proyecto_id'], unique=False)

    op.create_table('casos_prueba',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('proyecto_id', sa.Uuid(), nullable=False),
    sa.Column('modulo_objetivo_id', sa.Uuid(), nullable=True),
    sa.Column('nombre', sa.String(length=180), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=False),
    sa.Column('prioridad', sa.String(length=30), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('creado_por', sa.Uuid(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    sa.Column('actualizado_en', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['creado_por'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['modulo_objetivo_id'], ['modulos_objetivo.id'], ),
    sa.ForeignKeyConstraint(['proyecto_id'], ['proyectos.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('casos_prueba', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_casos_prueba_proyecto_id'), ['proyecto_id'], unique=False)

    op.create_table('ejecuciones',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('pipeline_id', sa.Uuid(), nullable=False),
    sa.Column('entorno_id', sa.Uuid(), nullable=False),
    sa.Column('origen', sa.String(length=60), nullable=False),
    sa.Column('estado', sa.String(length=60), nullable=False),
    sa.Column('fecha_encolado', sa.DateTime(timezone=True), nullable=False),
    sa.Column('fecha_inicio', sa.DateTime(timezone=True), nullable=True),
    sa.Column('fecha_fin', sa.DateTime(timezone=True), nullable=True),
    sa.Column('fecha_deteccion_primer_fallo', sa.DateTime(timezone=True), nullable=True),
    sa.Column('duracion_milisegundos', sa.Integer(), nullable=True),
    sa.Column('error_tecnico', sa.Text(), nullable=True),
    sa.Column('trabajador_id', sa.String(length=120), nullable=True),
    sa.Column('creado_por', sa.Uuid(), nullable=True),
    sa.ForeignKeyConstraint(['creado_por'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['entorno_id'], ['entornos.id'], ),
    sa.ForeignKeyConstraint(['pipeline_id'], ['pipelines.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('ejecuciones', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ejecuciones_entorno_id'), ['entorno_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_ejecuciones_estado'), ['estado'], unique=False)
        batch_op.create_index(batch_op.f('ix_ejecuciones_pipeline_id'), ['pipeline_id'], unique=False)

    op.create_table('monitores',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('proyecto_id', sa.Uuid(), nullable=False),
    sa.Column('entorno_id', sa.Uuid(), nullable=True),
    sa.Column('nombre', sa.String(length=180), nullable=False),
    sa.Column('tipo', sa.String(length=50), nullable=False),
    sa.Column('configuracion', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
    sa.Column('intervalo_recomendado_segundos', sa.Integer(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['entorno_id'], ['entornos.id'], ),
    sa.ForeignKeyConstraint(['proyecto_id'], ['proyectos.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('monitores', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_monitores_proyecto_id'), ['proyecto_id'], unique=False)

    op.create_table('programaciones',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('pipeline_id', sa.Uuid(), nullable=False),
    sa.Column('nombre', sa.String(length=180), nullable=False),
    sa.Column('tipo_frecuencia', sa.String(length=60), nullable=False),
    sa.Column('configuracion_frecuencia', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
    sa.Column('zona_horaria', sa.String(length=80), nullable=False),
    sa.Column('siguiente_ejecucion', sa.DateTime(timezone=True), nullable=True),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['pipeline_id'], ['pipelines.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('programaciones', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_programaciones_pipeline_id'), ['pipeline_id'], unique=False)

    op.create_table('secretos',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('proyecto_id', sa.Uuid(), nullable=False),
    sa.Column('entorno_id', sa.Uuid(), nullable=True),
    sa.Column('nombre', sa.String(length=120), nullable=False),
    sa.Column('tipo', sa.String(length=60), nullable=False),
    sa.Column('valor_cifrado', sa.Text(), nullable=False),
    sa.Column('creado_por', sa.Uuid(), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    sa.Column('actualizado_en', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['creado_por'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['entorno_id'], ['entornos.id'], ),
    sa.ForeignKeyConstraint(['proyecto_id'], ['proyectos.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('proyecto_id', 'entorno_id', 'nombre', name='uq_secreto_alcance_nombre')
    )
    with op.batch_alter_table('secretos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_secretos_proyecto_id'), ['proyecto_id'], unique=False)

    op.create_table('alertas',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('ejecucion_id', sa.Uuid(), nullable=False),
    sa.Column('tipo', sa.String(length=80), nullable=False),
    sa.Column('severidad', sa.String(length=60), nullable=False),
    sa.Column('estado_revision', sa.String(length=60), nullable=False),
    sa.Column('fecha_deteccion', sa.DateTime(timezone=True), nullable=False),
    sa.Column('fecha_reconocimiento', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reconocida_por', sa.Uuid(), nullable=True),
    sa.Column('clasificacion_manual', sa.String(length=60), nullable=False),
    sa.Column('observacion_revision', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['ejecucion_id'], ['ejecuciones.id'], ),
    sa.ForeignKeyConstraint(['reconocida_por'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('alertas', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_alertas_ejecucion_id'), ['ejecucion_id'], unique=False)

    op.create_table('notificaciones',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('ejecucion_id', sa.Uuid(), nullable=False),
    sa.Column('canal_notificacion_id', sa.Uuid(), nullable=True),
    sa.Column('estado', sa.String(length=60), nullable=False),
    sa.Column('fecha_solicitud', sa.DateTime(timezone=True), nullable=False),
    sa.Column('fecha_envio', sa.DateTime(timezone=True), nullable=True),
    sa.Column('intentos', sa.Integer(), nullable=False),
    sa.Column('error_sanitizado', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['canal_notificacion_id'], ['canales_notificacion.id'], ),
    sa.ForeignKeyConstraint(['ejecucion_id'], ['ejecuciones.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('notificaciones', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notificaciones_ejecucion_id'), ['ejecucion_id'], unique=False)

    op.create_table('pasos_caso_prueba',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('caso_prueba_id', sa.Uuid(), nullable=False),
    sa.Column('orden', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=80), nullable=False),
    sa.Column('nombre', sa.String(length=180), nullable=False),
    sa.Column('configuracion', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
    sa.Column('continuar_si_falla', sa.Boolean(), nullable=False),
    sa.Column('capturar_evidencia', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['caso_prueba_id'], ['casos_prueba.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('pasos_caso_prueba', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pasos_caso_prueba_caso_prueba_id'), ['caso_prueba_id'], unique=False)

    op.create_table('pasos_pipeline',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('pipeline_id', sa.Uuid(), nullable=False),
    sa.Column('orden', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=60), nullable=False),
    sa.Column('caso_prueba_id', sa.Uuid(), nullable=True),
    sa.Column('monitor_id', sa.Uuid(), nullable=True),
    sa.Column('nombre', sa.String(length=180), nullable=False),
    sa.Column('continuar_si_falla', sa.Boolean(), nullable=False),
    sa.Column('configuracion', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
    sa.ForeignKeyConstraint(['caso_prueba_id'], ['casos_prueba.id'], ),
    sa.ForeignKeyConstraint(['monitor_id'], ['monitores.id'], ),
    sa.ForeignKeyConstraint(['pipeline_id'], ['pipelines.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('pasos_pipeline', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pasos_pipeline_pipeline_id'), ['pipeline_id'], unique=False)

    op.create_table('resultados_paso',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('ejecucion_id', sa.Uuid(), nullable=False),
    sa.Column('paso_pipeline_id', sa.Uuid(), nullable=True),
    sa.Column('paso_caso_prueba_id', sa.Uuid(), nullable=True),
    sa.Column('tipo', sa.String(length=60), nullable=False),
    sa.Column('estado', sa.String(length=60), nullable=False),
    sa.Column('esperado', sa.Text(), nullable=False),
    sa.Column('obtenido', sa.Text(), nullable=False),
    sa.Column('mensaje', sa.Text(), nullable=False),
    sa.Column('fecha_inicio', sa.DateTime(timezone=True), nullable=False),
    sa.Column('fecha_fin', sa.DateTime(timezone=True), nullable=True),
    sa.Column('duracion_milisegundos', sa.Integer(), nullable=True),
    sa.Column('datos_tecnicos_sanitizados', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
    sa.ForeignKeyConstraint(['ejecucion_id'], ['ejecuciones.id'], ),
    sa.ForeignKeyConstraint(['paso_caso_prueba_id'], ['pasos_caso_prueba.id'], ),
    sa.ForeignKeyConstraint(['paso_pipeline_id'], ['pasos_pipeline.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('resultados_paso', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_resultados_paso_ejecucion_id'), ['ejecucion_id'], unique=False)

    op.create_table('evidencias',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('ejecucion_id', sa.Uuid(), nullable=False),
    sa.Column('resultado_paso_id', sa.Uuid(), nullable=True),
    sa.Column('tipo', sa.String(length=80), nullable=False),
    sa.Column('nombre_archivo', sa.String(length=255), nullable=False),
    sa.Column('ruta_relativa', sa.String(length=500), nullable=False),
    sa.Column('tipo_contenido', sa.String(length=120), nullable=False),
    sa.Column('tamano_bytes', sa.Integer(), nullable=False),
    sa.Column('hash_sha256', sa.String(length=64), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['ejecucion_id'], ['ejecuciones.id'], ),
    sa.ForeignKeyConstraint(['resultado_paso_id'], ['resultados_paso.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('evidencias', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_evidencias_ejecucion_id'), ['ejecucion_id'], unique=False)



def downgrade():
    with op.batch_alter_table('evidencias', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_evidencias_ejecucion_id'))

    op.drop_table('evidencias')
    with op.batch_alter_table('resultados_paso', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_resultados_paso_ejecucion_id'))

    op.drop_table('resultados_paso')
    with op.batch_alter_table('pasos_pipeline', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_pasos_pipeline_pipeline_id'))

    op.drop_table('pasos_pipeline')
    with op.batch_alter_table('pasos_caso_prueba', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_pasos_caso_prueba_caso_prueba_id'))

    op.drop_table('pasos_caso_prueba')
    with op.batch_alter_table('notificaciones', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notificaciones_ejecucion_id'))

    op.drop_table('notificaciones')
    with op.batch_alter_table('alertas', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_alertas_ejecucion_id'))

    op.drop_table('alertas')
    with op.batch_alter_table('secretos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_secretos_proyecto_id'))

    op.drop_table('secretos')
    with op.batch_alter_table('programaciones', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_programaciones_pipeline_id'))

    op.drop_table('programaciones')
    with op.batch_alter_table('monitores', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_monitores_proyecto_id'))

    op.drop_table('monitores')
    with op.batch_alter_table('ejecuciones', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ejecuciones_pipeline_id'))
        batch_op.drop_index(batch_op.f('ix_ejecuciones_estado'))
        batch_op.drop_index(batch_op.f('ix_ejecuciones_entorno_id'))

    op.drop_table('ejecuciones')
    with op.batch_alter_table('casos_prueba', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_casos_prueba_proyecto_id'))

    op.drop_table('casos_prueba')
    with op.batch_alter_table('pipelines', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_pipelines_proyecto_id'))

    op.drop_table('pipelines')
    with op.batch_alter_table('modulos_objetivo', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_modulos_objetivo_proyecto_id'))

    op.drop_table('modulos_objetivo')
    with op.batch_alter_table('mediciones_evaluacion', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_mediciones_evaluacion_proyecto_id'))

    op.drop_table('mediciones_evaluacion')
    with op.batch_alter_table('entornos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_entornos_proyecto_id'))

    op.drop_table('entornos')
    with op.batch_alter_table('canales_notificacion', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_canales_notificacion_proyecto_id'))

    op.drop_table('canales_notificacion')
    op.drop_table('usuarios_roles')
    op.drop_table('proyectos')
    op.drop_table('auditorias')
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_usuarios_correo'))

    op.drop_table('usuarios')
    op.drop_table('roles')
