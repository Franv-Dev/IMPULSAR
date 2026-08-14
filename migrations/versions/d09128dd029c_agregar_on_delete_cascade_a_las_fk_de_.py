"""Agregar ON DELETE CASCADE a las FK de reports

Revision ID: d09128dd029c
Revises: 6f4d273e25d2
Create Date: 2026-08-14 01:04:09.735197

Venia autogenerada contra MySQL, con los nombres que ese motor le pone solo a
las FK sin nombre (reports_ibfk_1 y reports_ibfk_3) escritos a mano. Sobre
SQLite esos nombres no existen (ahi las FK sin nombre directamente no lo
tienen), asi que "flask db upgrade" desde una base vacia moria aca con
ValueError: No such constraint: 'reports_ibfk_1'.

Ahora c24e5fc659b9 las crea con nombre explicito, y ademas esta migracion
averigua el nombre real en la base antes de dropear: asi funciona igual sobre
una base nueva (nombre explicito, cualquiera sea el motor) que sobre la MySQL
que ya venia con los nombres autogenerados.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd09128dd029c'
down_revision = '6f4d273e25d2'
branch_labels = None
depends_on = None


def _nombre_fk(tabla, columna):
    """El nombre real de la FK de esa columna, sea cual sea el motor.

    Se consulta antes de entrar en batch mode: sobre SQLite el batch recrea la
    tabla, y para sacarle una constraint hay que poder nombrarla.
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
    fk_post = _nombre_fk('reports', 'post_id')
    fk_review = _nombre_fk('reports', 'review_id')

    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.drop_constraint(fk_post, type_='foreignkey')
        batch_op.drop_constraint(fk_review, type_='foreignkey')
        # Las nuevas tambien con nombre, por lo mismo que las de c24e5fc659b9.
        batch_op.create_foreign_key(
            'fk_reports_post_id_posts', 'posts', ['post_id'], ['id'], ondelete='CASCADE'
        )
        batch_op.create_foreign_key(
            'fk_reports_review_id_reviews', 'reviews', ['review_id'], ['id'], ondelete='CASCADE'
        )


def downgrade():
    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.drop_constraint('fk_reports_post_id_posts', type_='foreignkey')
        batch_op.drop_constraint('fk_reports_review_id_reviews', type_='foreignkey')
        batch_op.create_foreign_key(
            'fk_reports_post_id_posts', 'posts', ['post_id'], ['id']
        )
        batch_op.create_foreign_key(
            'fk_reports_review_id_reviews', 'reviews', ['review_id'], ['id']
        )
