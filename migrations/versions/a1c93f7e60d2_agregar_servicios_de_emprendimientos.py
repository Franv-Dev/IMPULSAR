"""Agregar servicios de emprendimientos

Revision ID: a1c93f7e60d2
Revises: b8f5c2e41a97
Create Date: 2026-08-16 18:40:00.000000

Un trabajo a presupuestar, colgado del emprendimiento. Tabla propia y no una
columna mas en products: el precio es opcional (a presupuestar), tiene zona de
cobertura y arrastra el flujo de solicitudes de presupuesto.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1c93f7e60d2'
down_revision = 'b8f5c2e41a97'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'services',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('rubro', sa.String(length=40), nullable=False, server_default='otros'),
        sa.Column('titulo', sa.String(length=120), nullable=False),
        sa.Column('descripcion', sa.String(length=300), nullable=True),
        sa.Column('zona_cobertura', sa.String(length=120), nullable=True),
        # Nullable, a diferencia de products.precio: un servicio puede no tener
        # precio fijo. Numeric y no Float, por lo mismo que el producto.
        sa.Column('precio_estimado', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('disponible', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        # CASCADE y con nombre explicito, igual que la FK de products.
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE',
                                name='fk_services_post_id_posts'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('services', schema=None) as batch_op:
        # El listado del emprendimiento siempre consulta por post_id.
        batch_op.create_index(batch_op.f('ix_services_post_id'), ['post_id'], unique=False)
        # La busqueda por rubro es la unica consulta que no filtra por post_id.
        batch_op.create_index(batch_op.f('ix_services_rubro'), ['rubro'], unique=False)


def downgrade():
    # Solo drop_table, sin dropear los indices antes: el de post_id sostiene la
    # FK y MySQL no lo deja sacar mientras la FK exista ("Cannot drop index
    # ...: needed in a foreign key constraint"). Dropear la tabla se lleva sus
    # indices igual, en los dos motores. Mismo caso que products.
    op.drop_table('services')
