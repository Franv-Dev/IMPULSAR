"""Agregar ON DELETE CASCADE a favorites.post_id y messages.post_id

Revision ID: b30b4ba8d199
Revises: d09128dd029c
Create Date: 2026-08-14 01:22:18.181380

Mismo problema que d09128dd029c: venia autogenerada contra MySQL con
favorites_ibfk_1 y messages_ibfk_2 escritos a mano, nombres que ese motor le
pone solo a las FK sin nombre y que sobre SQLite no existen. No se veia porque
el upgrade desde cero moria una migracion antes.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b30b4ba8d199'
down_revision = 'd09128dd029c'
branch_labels = None
depends_on = None


def _nombre_fk(tabla, columna):
    """El nombre real de la FK de esa columna, sea cual sea el motor.

    Duplicada de d09128dd029c a proposito: una migracion es una foto de un
    momento y tiene que poder correr sola, sin depender de un modulo compartido
    que despues alguien mueva o cambie.
    """
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys(tabla):
        if fk["constrained_columns"] == [columna] and fk["name"]:
            return fk["name"]
    raise RuntimeError(
        f"No se encontro una FK con nombre sobre {tabla}.{columna}. Si la base "
        "es vieja y la tiene sin nombre, recrearla desde cero con las "
        "migraciones corregidas."
    )


def upgrade():
    fk_favorites = _nombre_fk('favorites', 'post_id')
    fk_messages = _nombre_fk('messages', 'post_id')

    with op.batch_alter_table('favorites', schema=None) as batch_op:
        batch_op.drop_constraint(fk_favorites, type_='foreignkey')
        batch_op.create_foreign_key(
            'fk_favorites_post_id_posts', 'posts', ['post_id'], ['id'], ondelete='CASCADE'
        )

    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_constraint(fk_messages, type_='foreignkey')
        batch_op.create_foreign_key(
            'fk_messages_post_id_posts', 'posts', ['post_id'], ['id'], ondelete='CASCADE'
        )


def downgrade():
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_constraint('fk_messages_post_id_posts', type_='foreignkey')
        batch_op.create_foreign_key(
            'fk_messages_post_id_posts', 'posts', ['post_id'], ['id']
        )

    with op.batch_alter_table('favorites', schema=None) as batch_op:
        batch_op.drop_constraint('fk_favorites_post_id_posts', type_='foreignkey')
        batch_op.create_foreign_key(
            'fk_favorites_post_id_posts', 'posts', ['post_id'], ['id']
        )
