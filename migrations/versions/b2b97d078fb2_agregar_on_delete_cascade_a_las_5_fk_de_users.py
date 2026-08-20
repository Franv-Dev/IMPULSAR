"""Agregar ON DELETE CASCADE a las 5 FK que quedaban apuntando a users

Revision ID: b2b97d078fb2
Revises: a2f7c50e19bd
Create Date: 2026-08-19 14:30:00.000000

Las cinco que faltaban: favorites.user_id, reviews.user_id,
reports.reporter_id, messages.client_id y messages.sender_id. Todas estaban en
NO ACTION (el default de MySQL, que ahi es lo mismo que RESTRICT), asi que
borrar un usuario con cualquier actividad fallaba con IntegrityError aunque sus
emprendimientos si se fueran por la cascada de posts.author (d4a2b6f19c73). El
unico borrado de usuarios que hay hoy, scripts/seed/borrado.py, lo esquivaba
borrando esas cinco tablas a mano y en orden.

Las dos de messages son la misma tabla y van juntas. La diferencia de
significado entre las dos sale sola de que el hilo se identifica por
(post_id, client_id):

  - borrar al cliente de una conversacion se lleva TODAS las filas donde es
    client_id, o sea el hilo entero, incluidos los mensajes que escribio el
    emprendedor del otro lado;
  - borrar a alguien que solo participo como sender_id se lleva unicamente los
    mensajes que escribio, y la conversacion sigue existiendo.

No hace falta expresar esa asimetria en la constraint: las dos son CASCADE a
nivel de fila y la asimetria la da a que columna apunta cada una. Si la misma
persona es las dos cosas en una fila, InnoDB borra la fila una sola vez, y si
se borran los dos lados de una conversacion, el orden no importa: lo que se
borro primero ya no esta cuando se evalua la segunda cascada.

El nombre de la FK se busca en la base antes de dropearla, igual que en
d4a2b6f19c73, d09128dd029c y b30b4ba8d199: una base creada desde cero las tiene
con el nombre que le pone el modelo, y la MySQL que ya venia de antes las tiene
como favorites_ibfk_2, reviews_ibfk_2, reports_ibfk_2, messages_ibfk_1 y
messages_ibfk_3, que es lo que ese motor le pone solo a las FK sin nombre.
"""
from contextlib import contextmanager

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2b97d078fb2'
down_revision = 'a2f7c50e19bd'
branch_labels = None
depends_on = None


# tabla -> [(columna, nombre nuevo de la constraint)]
FKS = {
    'favorites': [('user_id', 'fk_favorites_user_id_users')],
    'reviews': [('user_id', 'fk_reviews_user_id_users')],
    'reports': [('reporter_id', 'fk_reports_reporter_id_users')],
    'messages': [
        ('client_id', 'fk_messages_client_id_users'),
        ('sender_id', 'fk_messages_sender_id_users'),
    ],
}


def _nombre_fk(tabla, columna):
    """El nombre real de la FK de esa columna, sea cual sea el motor.

    Duplicada de d4a2b6f19c73, d09128dd029c y b30b4ba8d199 a proposito: una
    migracion es una foto de un momento y tiene que poder correr sola, sin
    depender de un modulo compartido que despues alguien mueva o cambie.
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
    dropea la original y renombra. Aca hace falta por reviews, que es una tabla
    referenciada (reports.review_id) y db.py deja PRAGMA foreign_keys=ON en
    toda conexion: el DROP TABLE reviews se lleva por delante la FK de reports
    y muere con "FOREIGN KEY constraint failed". Es el mismo caso que
    d4a2b6f19c73 con posts, y esta copiada de ahi por la misma razon que
    _nombre_fk.

    En MySQL no hace falta: ahi el batch es un ALTER TABLE comun, sin recrear.

    Al salir se hace detach de la conexion en vez de volver a prender el
    pragma: prenderlo no serviria de nada, porque en SQLite un PRAGMA es no-op
    si ya hay una transaccion abierta, y a esa altura el batch ya emitio DML.
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
    """Rehace las cinco FK con la politica pedida.

    Las dos de messages se dropean y se crean dentro del MISMO batch: en SQLite
    cada batch recrea la tabla entera, asi que hacerlas en dos batches seguidos
    recrearia messages dos veces al pedo, y en el medio la tabla quedaria con
    una sola de las dos politicas.
    """
    for tabla, columnas in FKS.items():
        nombres_viejos = [(_nombre_fk(tabla, columna), nuevo)
                          for columna, nuevo in columnas]

        with _sin_foreign_keys_en_sqlite():
            with op.batch_alter_table(tabla, schema=None) as batch_op:
                for viejo, _ in nombres_viejos:
                    batch_op.drop_constraint(viejo, type_='foreignkey')
                for (columna, nuevo) in columnas:
                    batch_op.create_foreign_key(
                        nuevo, 'users', [columna], ['id'], ondelete=ondelete
                    )


def upgrade():
    _rehacer('CASCADE')


def downgrade():
    # ondelete=None deja la FK sin clausula, que es exactamente como estaban:
    # NO ACTION en MySQL, el default del estandar.
    _rehacer(None)
