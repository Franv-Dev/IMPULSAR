"""Agregar ON DELETE CASCADE a reviews.post_id

Revision ID: c1f4a90b6e35
Revises: b2b97d078fb2
Create Date: 2026-08-19 15:10:00.000000

La ultima FK que apuntaba a posts sin CASCADE. Todas las demas ya lo tenian
(post_images, events, products, services, favorites, messages, reports), asi
que esta era la excepcion, no la regla.

Se ve recien ahora, con las cinco de b2b97d078fb2 arregladas: borrar un User
cuyo emprendimiento tiene una resenia de OTRA persona falla con
fk_reviews_post_id_posts. La cascada de posts.author (d4a2b6f19c73) borra el
post, y ahi el motor se encuentra con una resenia que sigue apuntando a el.

Que eso no se note al borrar desde la app es casualidad del camino que toma:
Post.reviews declara cascade="all, delete-orphan" del lado del ORM, asi que
db.session.delete(user) baja post por post y borra las resenias con DELETE
propios antes de que el motor evalue ninguna FK. A nivel base el problema
estaba igual, y cualquier borrado que no pase por la sesion -- un DELETE crudo
por SQL, una limpieza administrativa, codigo futuro -- se lo comia entero.

Va aparte de b2b97d078fb2 y no dentro: aquella es "las cinco FK a users" de
punta a punta (el nombre, el docstring y el helper que crea todo contra
'users'), y meterle una FK a posts obligaria a parametrizar la tabla destino
para que el downgrade siga siendo el espejo exacto del upgrade. Encadenada
sale mas limpio y cada una se puede revertir sola.
"""
from contextlib import contextmanager

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1f4a90b6e35'
down_revision = 'b2b97d078fb2'
branch_labels = None
depends_on = None


NOMBRE_NUEVO = 'fk_reviews_post_id_posts'


def _nombre_fk(tabla, columna):
    """El nombre real de la FK de esa columna, sea cual sea el motor.

    Duplicada de b2b97d078fb2 y compania a proposito: una migracion es una foto
    de un momento y tiene que poder correr sola, sin depender de un modulo
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

    Misma necesidad que en b2b97d078fb2: el batch recrea reviews (copia a una
    temporal, dropea la original y renombra), reviews esta referenciada por
    reports.review_id y db.py deja PRAGMA foreign_keys=ON en toda conexion, asi
    que el DROP TABLE moriria con "FOREIGN KEY constraint failed".

    En MySQL no hace falta: ahi el batch es un ALTER TABLE comun, sin recrear.
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
        # alembic todavia la necesita para escribir alembic_version.
        bind.detach()


def _rehacer(ondelete):
    viejo = _nombre_fk('reviews', 'post_id')

    with _sin_foreign_keys_en_sqlite():
        with op.batch_alter_table('reviews', schema=None) as batch_op:
            batch_op.drop_constraint(viejo, type_='foreignkey')
            batch_op.create_foreign_key(
                NOMBRE_NUEVO, 'posts', ['post_id'], ['id'], ondelete=ondelete
            )


def upgrade():
    _rehacer('CASCADE')


def downgrade():
    # ondelete=None deja la FK sin clausula, que es exactamente como estaba:
    # NO ACTION en MySQL, el default del estandar.
    _rehacer(None)
