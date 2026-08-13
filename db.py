from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow():
    """Fecha y hora actual en UTC, sin zona horaria.

    Se usa como default de las columnas DateTime. Equivale a datetime.utcnow(),
    que quedo deprecada en Python 3.12, pero devuelve lo mismo: un datetime
    naive en UTC, que es el formato en el que MySQL guarda un DATETIME.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
