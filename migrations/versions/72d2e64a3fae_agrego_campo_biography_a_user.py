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
from contextlib import contextmanager

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '72d2e64a3fae'
down_revision = None
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
    with _sin_foreign_keys_en_sqlite():
        inspector = sa.inspect(op.get_bind())

        if not _tiene_tabla_users(inspector) or not _tiene_columna_biography(inspector):
            return

        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.drop_column('biography')
