import sqlite3
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def _activar_foreign_keys_en_sqlite(dbapi_connection, connection_record):
    """SQLite no valida foreign keys por defecto (a diferencia de MySQL, que
    las usa en produccion). Sin esto, un test podia borrar una fila y romper
    una FK que en MySQL la base rechaza con IntegrityError: paso justo con
    reports.post_id/review_id, que en MySQL bloqueaban el borrado de un post
    reportado y en los tests (SQLite) pasaban sin que nadie lo notara.
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def utcnow():
    """Fecha y hora actual en UTC, sin zona horaria.

    Se usa como default de las columnas DateTime. Equivale a datetime.utcnow(),
    que quedo deprecada en Python 3.12, pero devuelve lo mismo: un datetime
    naive en UTC, que es el formato en el que MySQL guarda un DATETIME.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
