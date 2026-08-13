"""Agrego campo biography a User

Revision ID: 72d2e64a3fae
Revises:
Create Date: 2025-11-07 11:12:56.935865

Nota: esta migracion asume que la tabla 'users' ya existe, porque en su momento
las tablas se creaban con db.create_all() y no con migraciones. Sobre una base
vacia el ALTER TABLE fallaba y el historial no se podia aplicar desde cero.

Por eso ahora se saltea sola si la tabla no existe (base nueva): en ese caso la
migracion siguiente crea 'users' ya con la columna biography incluida. Para una
base que ya venia en uso, el comportamiento es exactamente el mismo de antes.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '72d2e64a3fae'
down_revision = None
branch_labels = None
depends_on = None


def _tiene_tabla_users(inspector):
    return "users" in set(inspector.get_table_names())


def _tiene_columna_biography(inspector):
    return "biography" in {col["name"] for col in inspector.get_columns("users")}


def upgrade():
    inspector = sa.inspect(op.get_bind())

    if not _tiene_tabla_users(inspector):
        return  # Base nueva: la crea la migracion 8f3c1d02b7a4.

    if _tiene_columna_biography(inspector):
        return  # Ya estaba (por ejemplo, creada con db.create_all()).

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('biography', sa.Text(), nullable=True))


def downgrade():
    inspector = sa.inspect(op.get_bind())

    if not _tiene_tabla_users(inspector) or not _tiene_columna_biography(inspector):
        return

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('biography')
