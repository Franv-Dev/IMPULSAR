"""Agregar estado a los emprendimientos

Revision ID: c7e41a9b2d35
Revises: fcf1046490ce
Create Date: 2026-09-15 19:40:12.336401

Una columna en posts: publicado o borrador. Es lo que hace funcionar el boton
"Guardar borrador" del formulario de emprendimiento, que hasta ahora estaba
maquetado y apagado.

EL server_default ES "publicado", Y NO ES UN DETALLE. La columna es NOT NULL y
la tabla ya tiene filas, asi que el default lo necesita el ALTER para poder
rellenarlas; pero ademas es lo que garantiza que esta migracion NO CAMBIE NADA
de lo que ya existe. Todos los emprendimientos publicados siguen publicados.
Con el default en "borrador" esta migracion habria vaciado el sitio entero: el
listado, el home, la busqueda y la API filtran por este estado.

El server_default se deja puesto despues del backfill (no se borra con un
segundo ALTER) por lo mismo que en services.disponible y products.disponible:
un INSERT que no mencione la columna --SQL a mano, un script de carga, un
fixture viejo-- tiene que caer en "publicado", que es el estado que no sorprende
a nadie. Lo contrario deja la puerta a filas invisibles sin que nadie las haya
pedido asi.

EL INDICE no es decorativo: todas las consultas publicas de posts filtran por
esta columna (ver app/blog/reglas.solo_publicados), asi que es la condicion que
mas veces se evalua en el sitio.

Downgrade: se va la columna y con ella la distincion. Los borradores que
hubiera pasan a ser emprendimientos publicados como cualquier otro, que es lo
unico que se puede hacer sin borrar datos del usuario.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7e41a9b2d35'
down_revision = 'fcf1046490ce'
branch_labels = None
depends_on = None


def upgrade():
    # batch_alter_table por SQLite, igual que el resto de las migraciones del
    # proyecto: alla un ALTER de verdad no existe y Alembic recrea la tabla.
    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'estado', sa.String(length=20),
            nullable=False, server_default='publicado',
        ))
        batch_op.create_index(
            batch_op.f('ix_posts_estado'), ['estado'], unique=False,
        )


def downgrade():
    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_posts_estado'))
        batch_op.drop_column('estado')
