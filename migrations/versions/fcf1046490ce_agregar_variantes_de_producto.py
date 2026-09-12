"""Agregar variantes de producto

Revision ID: fcf1046490ce
Revises: a41f7c3e9d05
Create Date: 2026-09-11 21:22:10.009124

Un producto puede venderse por combinacion de talle y color, cada una con su
stock y, si el vendedor quiere, con su propio precio. Dos tablas:

  producto_variante_opciones   que talles y que colores maneja ESE producto
  producto_variantes           una fila por combinacion realmente generada

NO SE TOCA products. Ni una columna nueva: el producto sin variantes queda
exactamente como estaba, con su precio fijo y su booleano `disponible`, que es
la condicion de la tanda. El stock numerico existe solo dentro de las
variantes.

LAS OPCIONES VAN EN UNA TABLA CON UN CAMPO `tipo` Y NO EN DOS TABLAS CHICAS:
un talle y un color tienen la misma forma, se usan en el mismo lugar y en el
mismo momento (son los dos ejes de la misma matriz), asi que dos tablas serian
el mismo modelo, la misma FK, el mismo UNIQUE y los mismos tests escritos dos
veces. El precio de la decision es que el tipo hay que validarlo, y eso lo
sostiene el CHECK y no la memoria de cada vista. El detalle completo esta en
models/producto_variante.py y en docs/VARIANTES.md.

UNIQUE(product_id, talle, color) ES LO QUE MAS HAY QUE MIRAR DE ESTA MIGRACION.
Es la constraint compuesta que impide dos veces la misma combinacion, y no
alcanza con chequear antes de insertar: entre ese SELECT y el INSERT hay una
ventana por la que pasan dos requests simultaneos.

Para que sirva SIEMPRE, talle y color son NOT NULL con server_default '': el
producto que usa un solo eje guarda el otro como cadena vacia y nunca como
NULL. En los dos motores un UNIQUE ignora las filas con NULL -- es la misma
propiedad que el proyecto aprovecha a favor en cupo_pendiente, cupo_activa y
cupo_aceptada --, asi que con NULL la regla se caeria justo en el caso de "solo
talles", que es el mas comun de todos.

Las dos FK nacen con ON DELETE CASCADE, que desde b2b97d078fb2 es la regla del
proyecto: borrar el producto se lleva sus opciones y sus variantes.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fcf1046490ce'
down_revision = 'a41f7c3e9d05'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('producto_variante_opciones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=10), nullable=False),
    sa.Column('valor', sa.String(length=40), nullable=False),
    sa.Column('orden', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint("tipo IN ('talle', 'color')", name='ck_producto_variante_opciones_tipo'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name='fk_producto_variante_opciones_product_id_products', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('product_id', 'tipo', 'valor', name='uq_producto_variante_opciones_valor')
    )
    with op.batch_alter_table('producto_variante_opciones', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_producto_variante_opciones_product_id'), ['product_id'], unique=False)

    op.create_table('producto_variantes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('talle', sa.String(length=40), server_default='', nullable=False),
    sa.Column('color', sa.String(length=40), server_default='', nullable=False),
    sa.Column('stock', sa.Integer(), server_default='0', nullable=False),
    sa.Column('precio_override', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('activo', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint('precio_override IS NULL OR precio_override >= 0', name='ck_producto_variantes_precio_no_negativo'),
    sa.CheckConstraint('stock >= 0', name='ck_producto_variantes_stock_no_negativo'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name='fk_producto_variantes_product_id_products', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('product_id', 'talle', 'color', name='uq_producto_variantes_combinacion')
    )
    with op.batch_alter_table('producto_variantes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_producto_variantes_activo'), ['activo'], unique=False)
        batch_op.create_index(batch_op.f('ix_producto_variantes_product_id'), ['product_id'], unique=False)


def downgrade():
    """Borra las dos tablas, y SOLO las tablas.

    Sin los drop_index que habia escrito el autogenerate, y esto es lo primero
    que se corrigio a mano: en MySQL un DROP INDEX sobre la columna de una
    foreign key falla con el error 1553 ("needed in a foreign key
    constraint"), asi que el downgrade autogenerado muere en la primera linea
    contra el motor de produccion. En SQLite pasa sin chistar, que es por lo
    que se cuela si no se prueba a mano.

    Y no hacen falta: DROP TABLE se lleva los indices de la tabla en los dos
    motores. Las dos tablas son hermanas (las dos cuelgan de products y ninguna
    de la otra), asi que el orden entre ellas da igual.
    """
    op.drop_table('producto_variantes')
    op.drop_table('producto_variante_opciones')
