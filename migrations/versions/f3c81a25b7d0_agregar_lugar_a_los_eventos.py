"""Agregar lugar a los eventos

Revision ID: f3c81a25b7d0
Revises: e9b3d71c4a08
Create Date: 2026-08-27 11:20:00.000000

Donde es el evento. Hasta ahora la cartelera mostraba fecha, hora y de que
emprendimiento sale, pero no el lugar: para una feria eso es justamente el
dato que falta para poder ir.

No se deriva de posts.address_street, que ya existe: la feria de una panaderia
normalmente no es en la panaderia. Usar la direccion del emprendimiento como
lugar del evento seria mostrar un dato equivocado con cara de dato real.

nullable=True y sin server_default: los eventos ya cargados no tienen lugar y
no hay de donde sacarselo. NULL es "no lo dijo", que es la verdad, y la
tarjeta simplemente no muestra la linea. Un server_default='' pondria una
cadena vacia que despues no se distingue de "lo dejo en blanco a proposito".

batch_alter_table por el mismo motivo que el resto de las migraciones del
proyecto: SQLite no tiene ALTER TABLE ADD COLUMN para todos los casos y
Alembic lo resuelve recreando la tabla. En MySQL el batch es un no-op y sale
un ALTER normal.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3c81a25b7d0'
down_revision = 'e9b3d71c4a08'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('lugar', sa.String(length=120), nullable=True))


def downgrade():
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_column('lugar')
