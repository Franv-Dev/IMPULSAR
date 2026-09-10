"""Agregar ubicacion textual al perfil

Revision ID: b7e2d05c1943
Revises: a3f1c9d47b52
Create Date: 2026-08-14 02:40:00.000000

users.location es texto libre ("Maipú, Mendoza") para mostrar en el perfil, y
no reemplaza a users.address_street: esa sigue siendo la direccion que se
geocodifica para el mapa. Por eso se agrega una columna nueva en vez de
reutilizar la que ya existe.
"""
from contextlib import contextmanager

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7e2d05c1943'
down_revision = 'a3f1c9d47b52'
branch_labels = None
depends_on = None


@contextmanager
def _sin_foreign_keys_en_sqlite():
    """Apaga la verificacion de FK mientras dura el batch, solo en SQLite.

    En SQLite un batch_alter_table recrea la tabla: copia a una temporal,
    dropea la original y renombra. Aca hace falta porque users es una tabla
    referenciada y db.py deja PRAGMA foreign_keys=ON en toda conexion: si ya
    hay filas hijas, el DROP TABLE users muere con "FOREIGN KEY constraint
    failed". Es el mismo caso que d4a2b6f19c73 con posts, b2b97d078fb2 con
    reviews y a3f1c9d47b52 con users, y esta copiada de ahi por la misma razon
    que se duplica _nombre_fk en esas: una migracion es una foto de un momento
    y tiene que poder correr sola.

    En MySQL no hace falta: ahi el batch es un ALTER TABLE comun, sin recrear.

    Al salir se hace detach de la conexion en vez de volver a prender el
    pragma: prenderlo no serviria de nada, porque en SQLite un PRAGMA es no-op
    si ya hay una transaccion abierta, y a esa altura el batch ya emitio DML.
    Por lo mismo, el bloque tiene que abrirse ANTES de cualquier DML de la
    migracion, no solo antes del batch que recrea.
    """
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        yield
        return

    bind.exec_driver_sql('PRAGMA foreign_keys=OFF')

    # El OFF se relee para confirmar que agarro. En SQLite un PRAGMA es un
    # no-op SILENCIOSO si ya hay una transaccion abierta: no tira error, no
    # avisa, simplemente no apaga nada. Sin este chequeo el sintoma aparece
    # recien mas adelante, como un "FOREIGN KEY constraint failed" sobre un
    # DROP TABLE que no explica por que las FK seguian prendidas.
    if bind.exec_driver_sql('PRAGMA foreign_keys').scalar():
        raise RuntimeError(
            "PRAGMA foreign_keys sigue en ON despues del OFF: hay una "
            "transaccion abierta antes de este punto y el pragma quedo en "
            "no-op. Este bloque tiene que abrirse antes de cualquier DML de "
            "la migracion."
        )

    try:
        yield
    finally:
        # detach() y no invalidate(): invalidar tira la conexion en el acto y
        # alembic todavia la necesita para escribir alembic_version.
        bind.detach()


def upgrade():
    # Un solo paso, a diferencia de la del slug: la columna es nullable y no
    # hay nada que completar en las filas que ya existen.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('location', sa.String(length=120), nullable=True))


def downgrade():
    with _sin_foreign_keys_en_sqlite():
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.drop_column('location')
