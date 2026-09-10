"""Agregar favoritos de productos

Revision ID: a4c17b8e6d20
Revises: b6d29e4f1a83
Create Date: 2026-09-09 12:00:00.000000

El corazon de las tarjetas del catalogo publico. Va en su propia tabla y no
como una columna nullable mas en favorites: ver el docstring de
models/product_favorite.py.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4c17b8e6d20'
down_revision = 'b6d29e4f1a83'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'product_favorites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('created', sa.DateTime(), nullable=False),
        # CASCADE y con nombre explicito en las dos, desde el vamos: sin
        # CASCADE, MySQL usa RESTRICT y borrar un usuario (o un producto que
        # alguien marco) falla con IntegrityError; sin nombre, la FK se llama
        # distinto en cada motor y ninguna migracion posterior puede dropearla.
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE',
                                name='fk_product_favorites_user_id_users'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE',
                                name='fk_product_favorites_product_id_products'),
        sa.PrimaryKeyConstraint('id'),
        # Dos clicks casi simultaneos en el corazon insertarian dos filas: la
        # consulta de "ya lo tiene?" pasa las dos veces antes del primer
        # INSERT. Esto es lo que de verdad lo impide.
        sa.UniqueConstraint('user_id', 'product_id',
                            name='uq_product_favorite_user_product'),
    )
    with op.batch_alter_table('product_favorites', schema=None) as batch_op:
        # "Mis favoritos" consulta por usuario; el catalogo pregunta cuales de
        # los productos de la pagina estan marcados.
        batch_op.create_index(batch_op.f('ix_product_favorites_user_id'),
                              ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_product_favorites_product_id'),
                              ['product_id'], unique=False)


def downgrade():
    # Solo drop_table, sin dropear los indices antes: sostienen las FK y MySQL
    # no deja sacarlos mientras las FK existan ("Cannot drop index ...: needed
    # in a foreign key constraint"). Dropear la tabla se lleva sus indices en
    # los dos motores. Mismo criterio que b8f5c2e41a97.
    op.drop_table('product_favorites')
