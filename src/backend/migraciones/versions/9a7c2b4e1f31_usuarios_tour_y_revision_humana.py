from alembic import op
import sqlalchemy as sa


revision = "9a7c2b4e1f31"
down_revision = "21c381edea85"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tour_completado", sa.Boolean(), server_default=sa.false(), nullable=False))

    with op.batch_alter_table("casos_prueba", schema=None) as batch_op:
        batch_op.add_column(sa.Column("requiere_revision_humana", sa.Boolean(), server_default=sa.false(), nullable=False))

    op.create_table(
        "revisiones_ejecucion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ejecucion_id", sa.Uuid(), nullable=False),
        sa.Column("clasificacion", sa.String(length=60), nullable=False),
        sa.Column("comentario", sa.Text(), nullable=False),
        sa.Column("revisado_por", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ejecucion_id"], ["ejecuciones.id"]),
        sa.ForeignKeyConstraint(["revisado_por"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("revisiones_ejecucion", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_revisiones_ejecucion_ejecucion_id"), ["ejecucion_id"], unique=False)

    op.create_table(
        "revisiones_paso",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resultado_paso_id", sa.Uuid(), nullable=False),
        sa.Column("clasificacion", sa.String(length=60), nullable=False),
        sa.Column("comentario", sa.Text(), nullable=False),
        sa.Column("revisado_por", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["resultado_paso_id"], ["resultados_paso.id"]),
        sa.ForeignKeyConstraint(["revisado_por"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("revisiones_paso", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_revisiones_paso_resultado_paso_id"), ["resultado_paso_id"], unique=False)


def downgrade():
    with op.batch_alter_table("revisiones_paso", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_revisiones_paso_resultado_paso_id"))
    op.drop_table("revisiones_paso")

    with op.batch_alter_table("revisiones_ejecucion", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_revisiones_ejecucion_ejecucion_id"))
    op.drop_table("revisiones_ejecucion")

    with op.batch_alter_table("casos_prueba", schema=None) as batch_op:
        batch_op.drop_column("requiere_revision_humana")

    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.drop_column("tour_completado")
