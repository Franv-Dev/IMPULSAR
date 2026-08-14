"""Agregar slug de usuario para la URL del perfil

Revision ID: a3f1c9d47b52
Revises: 499b808ef8ab
Create Date: 2026-08-14 02:10:00.000000

La columna se agrega en tres pasos y no en uno solo: como es NOT NULL y
UNIQUE, crearla directamente con esas restricciones falla en cualquier base
que ya tenga usuarios. Primero entra nullable, despues se completa fila por
fila, y recien entonces se le ponen las restricciones.
"""
from alembic import op
import sqlalchemy as sa

from services.slugs import generar_slug, slug_disponible


# revision identifiers, used by Alembic.
revision = 'a3f1c9d47b52'
down_revision = '499b808ef8ab'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('slug', sa.String(length=60), nullable=True))

    # Backfill: los usuarios que ya existen nunca pasaron por la validacion de
    # registro, asi que pueden tener nombres con tildes, espacios o solo
    # numeros. generar_slug + slug_disponible los normaliza y desambigua.
    conexion = op.get_bind()
    filas = conexion.execute(
        sa.text("SELECT id, username FROM users ORDER BY id")
    ).fetchall()

    asignados = set()
    for user_id, username in filas:
        slug = slug_disponible(
            generar_slug(username),
            lambda candidato: candidato in asignados,
        )
        asignados.add(slug)
        conexion.execute(
            sa.text("UPDATE users SET slug = :slug WHERE id = :id"),
            {"slug": slug, "id": user_id},
        )

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('slug', existing_type=sa.String(length=60), nullable=False)
        batch_op.create_index(batch_op.f('ix_users_slug'), ['slug'], unique=True)


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_slug'))
        batch_op.drop_column('slug')
