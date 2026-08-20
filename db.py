import sqlite3
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()


def _activar_foreign_keys(dbapi_connection):
    """PRAGMA foreign_keys=ON, si la conexion es de SQLite."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@event.listens_for(Engine, "connect")
def _activar_foreign_keys_al_conectar(dbapi_connection, connection_record):
    """SQLite no valida foreign keys por defecto (a diferencia de MySQL, que
    las usa en produccion). Sin esto, un test podia borrar una fila y romper
    una FK que en MySQL la base rechaza con IntegrityError: paso justo con
    reports.post_id/review_id, que en MySQL bloqueaban el borrado de un post
    reportado y en los tests (SQLite) pasaban sin que nadie lo notara.
    """
    _activar_foreign_keys(dbapi_connection)


@event.listens_for(Engine, "checkout")
def _activar_foreign_keys_al_sacar_del_pool(dbapi_connection, connection_record,
                                            connection_proxy):
    """Lo mismo, pero cada vez que el pool entrega una conexion ya abierta.

    El pragma es por conexion y vive mientras vive la conexion, asi que el
    listener de "connect" solo lo garantiza la primera vez: si alguien lo apaga
    y despues devuelve la conexion al pool, la siguiente que la saque la recibe
    con las FK desactivadas y no se entera. Pasa de verdad: la migracion
    d4a2b6f19c73 tiene que apagarlas para poder recrear posts en SQLite, y en
    SQLite un PRAGMA no hace nada si ya hay una transaccion abierta, asi que
    volver a prenderlo ahi no es algo en lo que se pueda confiar. Se reafirma
    aca, que es el unico lugar por el que pasan todas.
    """
    _activar_foreign_keys(dbapi_connection)


@event.listens_for(Engine, "begin")
def _activar_foreign_keys_al_empezar_transaccion(conexion):
    """Lo mismo, pero al abrir cada transaccion sobre una conexion ya en uso.

    Los dos listeners de arriba solo corren cuando la conexion se abre o se
    saca del pool, y eso deja afuera justo el caso de las migraciones. Una
    corrida de alembic ('flask db upgrade' o 'db downgrade') agarra UNA
    conexion y la usa para todas las migraciones de esa corrida, una atras de
    la otra. Varias de esas migraciones tienen que apagar el pragma para poder
    recrear una tabla referenciada en SQLite (ver a3f1c9d47b52 y las que la
    imitan), y al terminar hacen bind.detach(). Pero detach NO cierra la
    conexion: solo hace que no vuelva al pool. Alembic sigue usando la misma,
    y sin esto quedaba apagado para TODAS las migraciones siguientes de esa
    corrida, no solo para la que lo apago.

    Eso no rompia nada por si solo -son operaciones DDL-, pero volvia inutil
    cualquier verificacion hecha bajando desde head: una migracion tardia se
    veia sana solo porque otra anterior le habia apagado las FK. Asi se
    escondio el borrado mudo de service_requests de a2f7c50e19bd, que solo
    aparece corriendo ese downgrade aislado.

    Se engancha en "begin" y no en "commit" porque un PRAGMA no hace nada si
    ya hay una transaccion abierta. Alembic hace commit despues de cada
    migracion y la siguiente abre una nueva, y en SQLite el BEGIN de verdad se
    difiere hasta el primer DML: en el momento en que corre este listener
    todavia no hay transaccion, asi que el pragma si toma. Y como tampoco la
    abre este PRAGMA, la migracion que despues necesite apagarlo lo sigue
    pudiendo hacer.
    """
    if conexion.dialect.name != "sqlite":
        return
    conexion.exec_driver_sql("PRAGMA foreign_keys=ON")


def utcnow():
    """Fecha y hora actual en UTC, sin zona horaria.

    Se usa como default de las columnas DateTime. Equivale a datetime.utcnow(),
    que quedo deprecada en Python 3.12, pero devuelve lo mismo: un datetime
    naive en UTC, que es el formato en el que MySQL guarda un DATETIME.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
