"""Agregar catalogo de productos

Revision ID: b8f5c2e41a97
Revises: d4a2b6f19c73
Create Date: 2026-08-14 22:30:00.000000

Un producto o servicio con precio, colgado del emprendimiento. Catalogo, no
tienda: no hay stock ni pagos.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8f5c2e41a97'
down_revision = 'd4a2b6f19c73'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=120), nullable=False),
        sa.Column('descripcion', sa.String(length=300), nullable=True),
        # Numeric y no Float: con Float un precio de 1999.95 vuelve de la base
        # como 1999.9499999 y cualquier suma arrastra el error.
        sa.Column('precio', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('foto', sa.String(length=100), nullable=True),
        sa.Column('disponible', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        # CASCADE y con nombre explicito desde el vamos, que es justo lo que
        # hubo que ir a arreglar despues en el resto de las tablas: sin CASCADE
        # MySQL usa RESTRICT y borrar un emprendimiento con productos falla, y
        # sin nombre la FK se llama distinto en cada motor (products_ibfk_1 en
        # MySQL, nada en SQLite) y ninguna migracion posterior puede dropearla.
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE',
                                name='fk_products_post_id_posts'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('products', schema=None) as batch_op:
        # El catalogo siempre se consulta por emprendimiento.
        batch_op.create_index(batch_op.f('ix_products_post_id'), ['post_id'], unique=False)


def downgrade():
    # Solo drop_table, sin dropear el indice antes. El indice lo autogenera
    # alembic en el downgrade, pero sobre MySQL falla con "Cannot drop index
    # 'ix_products_post_id': needed in a foreign key constraint": el indice
    # sostiene la FK y no se puede sacar mientras la FK exista. Dropear la
    # tabla se lleva sus indices igual, en los dos motores.
    op.drop_table('products')
