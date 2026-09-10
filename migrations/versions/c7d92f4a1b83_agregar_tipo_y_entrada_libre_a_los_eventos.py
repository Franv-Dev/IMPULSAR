"""Agregar tipo y entrada libre a los eventos

Revision ID: c7d92f4a1b83
Revises: a4c17b8e6d20
Create Date: 2026-09-09 16:10:00.000000

Las dos columnas que pide la cartelera rediseñada (disenio-eventos/). Los dos
son filtros: "¿qué hay para hacer el sábado?" se contesta primero por tipo --no
es lo mismo pasar por una feria que anotarse a un taller-- y despues por si se
entra sin pagar.

`tipo` NULLABLE Y SIN server_default, igual que `lugar` en f3c81a25b7d0 y por la
misma razon: los eventos ya cargados no tienen tipo y no hay de donde sacarselo.
Ponerles 'feria' a todos etiquetaria de mentira lo que quiza era un taller, y un
dato equivocado con cara de dato real es peor que no tenerlo. NULL es "no lo
dijo": la tarjeta no dibuja el chip y el filtro por tipo no lo cuenta. El
formulario si lo exige para los nuevos, asi que el NULL se agota solo.

`entrada_libre` NOT NULL con server_default "0", y la asimetria con `tipo` es
deliberada: el chip "Entrada libre" solo se dibuja cuando es True, asi que False
no afirma nada -- es "no dice" -- mientras que marcarle entrada libre a un
taller pago prometeria gratis lo que se cobra. Por eso el default seguro es el
False y no hace falta un tercer estado.

server_default "0" y no sa.false(): es el string que ya usan las otras columnas
booleanas del proyecto (services.disponible, services.verificado), y funciona
igual en SQLite y en MySQL.

El indice va sobre `tipo` porque la cartelera filtra por ahi, igual que ya lo
hace por fecha. Sobre `entrada_libre` NO: un booleano con dos valores no le
sirve a ningun plan de consulta, el motor barre igual.

batch_alter_table por el mismo motivo que el resto de las migraciones del
proyecto: en SQLite Alembic recrea la tabla, y en MySQL el batch es un no-op y
sale un ALTER normal.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7d92f4a1b83'
down_revision = 'a4c17b8e6d20'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tipo', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column(
            'entrada_libre', sa.Boolean(), nullable=False, server_default='0'
        ))
        batch_op.create_index(
            batch_op.f('ix_events_tipo'), ['tipo'], unique=False
        )


def downgrade():
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_events_tipo'))
        batch_op.drop_column('entrada_libre')
        batch_op.drop_column('tipo')
