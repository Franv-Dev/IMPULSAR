"""Agregar slug de usuario para la URL del perfil

Revision ID: a3f1c9d47b52
Revises: 499b808ef8ab
Create Date: 2026-08-14 02:10:00.000000

La columna se agrega en tres pasos y no en uno solo: como es NOT NULL y
UNIQUE, crearla directamente con esas restricciones falla en cualquier base
que ya tenga usuarios. Primero entra nullable, despues se completa fila por
fila, y recien entonces se le ponen las restricciones.
"""
from contextlib import contextmanager

from alembic import op
import sqlalchemy as sa

from services.slugs import generar_slug, slug_disponible


# revision identifiers, used by Alembic.
revision = 'a3f1c9d47b52'
down_revision = '499b808ef8ab'
branch_labels = None
depends_on = None


@contextmanager
def _sin_foreign_keys_en_sqlite():
    """Apaga la verificacion de FK mientras dura el batch, solo en SQLite.

    En SQLite un batch_alter_table recrea la tabla: copia a una temporal,
    dropea la original y renombra. Aca hace falta porque users es una tabla
    referenciada (posts.author, reviews.user_id, favorites.user_id,
    reports.reporter_id, messages.client_id/sender_id) y db.py deja
    PRAGMA foreign_keys=ON en toda conexion: si ya hay filas hijas, el
    DROP TABLE users muere con "FOREIGN KEY constraint failed". Es el mismo
    caso que d4a2b6f19c73 con posts y b2b97d078fb2 con reviews, y esta copiada
    de ahi por la misma razon que se duplica _nombre_fk en esas dos: una
    migracion es una foto de un momento y tiene que poder correr sola.

    En MySQL no hace falta: ahi el batch es un ALTER TABLE comun, sin recrear.

    Al salir se hace detach de la conexion en vez de volver a prender el
    pragma: prenderlo no serviria de nada, porque en SQLite un PRAGMA es no-op
    si ya hay una transaccion abierta, y a esa altura el batch ya emitio DML.
    Por lo mismo, el bloque tiene que abrirse ANTES de cualquier DML de la
    migracion, no solo antes del batch que recrea (ver upgrade()).
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
    # DROP TABLE que no explica por que las FK seguian prendidas. Mejor
    # explotar aca, donde el mensaje dice cual es el problema real.
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
    # Las FK se apagan alrededor de TODO el upgrade y no solo del batch que
    # recrea la tabla, que es como lo hacen d4a2b6f19c73 y b2b97d078fb2.
    # La diferencia esta en el backfill: en SQLite un PRAGMA es un no-op
    # silencioso si ya hay una transaccion abierta, y los UPDATE del paso 2
    # abren una. Poniendo el OFF recien antes del tercer paso no se entera
    # nadie -no falla, simplemente no hace nada- y el DROP TABLE users sigue
    # muriendo con "FOREIGN KEY constraint failed". Al entrar a upgrade()
    # todavia no se emitio DML, asi que ahi el OFF si toma.
    with _sin_foreign_keys_en_sqlite():
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.add_column(sa.Column('slug', sa.String(length=60), nullable=True))

        # Backfill: los usuarios que ya existen nunca pasaron por la validacion
        # de registro, asi que pueden tener nombres con tildes, espacios o solo
        # numeros. generar_slug + slug_disponible los normaliza y desambigua.
        conexion = op.get_bind()
        filas = conexion.execute(
            sa.text("SELECT id, username FROM users ORDER BY id")
        ).fetchall()

        asignados = set()
        for user_id, username in filas:
            slug = slug_disponible(
                generar_slug(username),
                lambda candidato: candidato in asignados,
            )
            asignados.add(slug)
            conexion.execute(
                sa.text("UPDATE users SET slug = :slug WHERE id = :id"),
                {"slug": slug, "id": user_id},
            )

        # El NOT NULL y el indice van en el MISMO batch: en SQLite cada batch
        # recrea la tabla entera, asi que separarlos seria recrear users dos
        # veces al pedo. Este es el paso que necesita las FK apagadas.
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.alter_column('slug', existing_type=sa.String(length=60), nullable=False)
            batch_op.create_index(batch_op.f('ix_users_slug'), ['slug'], unique=True)


def downgrade():
    # drop_column tambien recrea la tabla en SQLite, mismo motivo que arriba.
    with _sin_foreign_keys_en_sqlite():
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_users_slug'))
            batch_op.drop_column('slug')
