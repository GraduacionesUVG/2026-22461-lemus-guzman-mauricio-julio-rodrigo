from alembic import op
import sqlalchemy as sa


revision = "c4f6a1b2d9e3"
down_revision = "9a7c2b4e1f31"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "informes_ejecucion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ejecucion_id", sa.Uuid(), nullable=False),
        sa.Column("ruta_relativa", sa.String(length=500), nullable=False),
        sa.Column("nombre_archivo", sa.String(length=255), nullable=False),
        sa.Column("tipo_contenido", sa.String(length=120), nullable=False),
        sa.Column("tamano_bytes", sa.Integer(), nullable=False),
        sa.Column("hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("generado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("zona_horaria", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["ejecucion_id"], ["ejecuciones.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("informes_ejecucion", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_informes_ejecucion_ejecucion_id"), ["ejecucion_id"], unique=False)


def downgrade():
    with op.batch_alter_table("informes_ejecucion", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_informes_ejecucion_ejecucion_id"))
    op.drop_table("informes_ejecucion")
