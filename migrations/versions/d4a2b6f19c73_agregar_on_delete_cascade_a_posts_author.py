"""Agregar ON DELETE CASCADE a posts.author

Revision ID: d4a2b6f19c73
Revises: a7d4e91f5c02
Create Date: 2026-08-14 21:40:00.000000

Borrar un usuario fallaba: el ORM intentaba dejar sus emprendimientos huerfanos
con un UPDATE posts SET author=NULL, y la columna es NOT NULL. La decision es
que si se borra un usuario se borren tambien sus emprendimientos, coherente con
que todo lo que cuelga de un emprendimiento (resenias, eventos, fotos,
favoritos, mensajes, reportes) ya se va con el.

El nombre de la FK se busca en la base antes de dropearla, igual que en
d09128dd029c y b30b4ba8d199: una base creada desde cero la tiene como
fk_posts_author_users (8f3c1d02b7a4 ahora la nombra), pero la MySQL que ya
venia de antes la tiene como posts_ibfk_1, el nombre que ese motor le pone solo
a las FK sin nombre.
"""
from contextlib import contextmanager

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4a2b6f19c73'
down_revision = 'a7d4e91f5c02'
branch_labels = None
depends_on = None


def _nombre_fk(tabla, columna):
    """El nombre real de la FK de esa columna, sea cual sea el motor.

    Duplicada de d09128dd029c y b30b4ba8d199 a proposito: una migracion es una
    foto de un momento y tiene que poder correr sola, sin depender de un modulo
    compartido que despues alguien mueva o cambie.
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


@contextmanager
def _sin_foreign_keys_en_sqlite():
    """Apaga la verificacion de FK mientras dura el batch, solo en SQLite.

    En SQLite un batch_alter_table recrea la tabla: copia a una temporal,
    dropea la original y renombra. Con posts eso no salia, porque es una tabla
    referenciada (events, post_images, favorites, messages, reports, reviews) y
    db.py deja PRAGMA foreign_keys=ON en toda conexion: el DROP TABLE posts se
    lleva por delante las FK de las hijas y muere con "FOREIGN KEY constraint
    failed". Las migraciones anteriores que usan batch (d09128dd029c,
    b30b4ba8d199) no se toparon con esto porque tocan tablas que no referencia
    nadie.

    EL ERROR RUIDOSO LO APORTA UNA SOLA DE LAS SEIS. En este punto de la cadena
    events, post_images, favorites, messages y reports ya estan en ON DELETE
    CASCADE, y una hija que cascadea no hace fallar nada: el DROP TABLE la vacia
    en silencio. La que rompe fuerte es reviews.post_id, que todavia esta en NO
    ACTION (recien la arregla c1f4a90b6e35). O sea que la excepcion aparece
    porque hay reseñas cargadas; en una base sin reseñas esta misma migracion no
    fallaria, se llevaria puestas las otras cinco sin decir nada. En los dos
    casos la solucion es la misma y es esta: apagar las FK.

    En MySQL no hace falta: ahi el batch es un ALTER TABLE comun, sin recrear.

    Al salir se hace detach de la conexion en vez de volver a prender el
    pragma: prenderlo no serviria de nada, porque en SQLite un PRAGMA es no-op
    si ya hay una transaccion abierta, y a esa altura el batch ya emitio DML
    (el INSERT que copia las filas). Al entrar todavia no hay transaccion, por
    eso el OFF si toma. Con el detach, el pool descarta esta conexion en vez de
    reusarla con las FK apagadas, y la proxima se abre de cero (db.py las
    prende al conectar y al sacarlas del pool).
    """
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        yield
        return

    bind.exec_driver_sql('PRAGMA foreign_keys=OFF')
    try:
        yield
    finally:
        # detach() y no invalidate(): invalidar tira la conexion en el acto y
        # alembic todavia la necesita para escribir alembic_version (probado:
        # con invalidate() la version se queda en la revision anterior).
        # detach la saca del pool pero la deja usable hasta que se cierre, que
        # es justo lo que hace falta: nadie mas la va a recibir con las FK
        # apagadas.
        bind.detach()


def upgrade():
    fk_author = _nombre_fk('posts', 'author')

    with _sin_foreign_keys_en_sqlite():
        with op.batch_alter_table('posts', schema=None) as batch_op:
            batch_op.drop_constraint(fk_author, type_='foreignkey')
            batch_op.create_foreign_key(
                'fk_posts_author_users', 'users', ['author'], ['id'], ondelete='CASCADE'
            )


def downgrade():
    with _sin_foreign_keys_en_sqlite():
        with op.batch_alter_table('posts', schema=None) as batch_op:
            batch_op.drop_constraint('fk_posts_author_users', type_='foreignkey')
            batch_op.create_foreign_key(
                'fk_posts_author_users', 'users', ['author'], ['id']
            )
