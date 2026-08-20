"""Agregar ubicacion textual al perfil

Revision ID: b7e2d05c1943
Revises: a3f1c9d47b52
Create Date: 2026-08-14 02:40:00.000000

users.location es texto libre ("Maipú, Mendoza") para mostrar en el perfil, y
no reemplaza a users.address_street: esa sigue siendo la direccion que se
geocodifica para el mapa. Por eso se agrega una columna nueva en vez de
reutilizar la que ya existe.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7e2d05c1943'
down_revision = 'a3f1c9d47b52'
branch_labels = None
depends_on = None


def upgrade():
    # Un solo paso, a diferencia de la del slug: la columna es nullable y no
    # hay nada que completar en las filas que ya existen.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('location', sa.String(length=120), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('location')
