"""CHECK de precios validos en products, services y service_requests

Revision ID: a4e18c37d9b2
Revises: f3c81a25b7d0
Create Date: 2026-09-02

Los tres precios del proyecto ya se validan en services/precios.py, que es
donde el usuario recibe un mensaje entendible. Esto es la red de abajo, con el
mismo criterio que ck_review_rating: el formulario no es el unico camino a las
tablas (estan el seed, un script suelto, una consola de la base) y una fila con
precio negativo no se nota hasta que alguien suma un catalogo.

Las tres reglas, y por que no son la misma:

  products.precio            >= 0   (un producto gratis es una oferta real)
  services.precio_estimado   NULL o > 0
  service_requests.respuesta_precio  NULL o > 0

En los servicios "sin cargo" no se escribe con un cero sino dejando la columna
en NULL, que es "a presupuestar"; un 0 ahi seria un precio cerrado de cero
pesos. El NULL es parte de la regla, no una excusa: las dos columnas son
nullable a proposito (ver los comentarios de los modelos).

OJO CON MYSQL VIEJO: un CHECK con condicion recien se valida desde MySQL
8.0.16. En versiones anteriores el ALTER se acepta y la constraint se ignora en
silencio, asi que la garantia dura queda en SQLite y en MySQL moderno. Es el
mismo limite que ya anota Service.duracion_turno_minutos, y no cambia nada de
lo de arriba: la validacion que ve el usuario sigue siendo la de precios.py.
"""
from contextlib import contextmanager

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4e18c37d9b2'
down_revision = 'f3c81a25b7d0'
branch_labels = None
depends_on = None


# Tabla -> (nombre de la constraint, condicion).
CHECKS = (
    ("products", "ck_products_precio_no_negativo", "precio >= 0"),
    ("services", "ck_services_precio_estimado_positivo",
     "precio_estimado IS NULL OR precio_estimado > 0"),
    ("service_requests", "ck_service_requests_respuesta_precio_positivo",
     "respuesta_precio IS NULL OR respuesta_precio > 0"),
)


@contextmanager
def _sin_foreign_keys_en_sqlite():
    """Apaga la verificacion de FK mientras dura el batch, solo en SQLite.

    En SQLite un batch_alter_table recrea la tabla: copia a una temporal,
    dropea la original y renombra. `services` es una tabla referenciada
    (service_requests y turnos cuelgan de ella) y db.py deja PRAGMA
    foreign_keys=ON en toda conexion, asi que con filas hijas cargadas el DROP
    muere con "FOREIGN KEY constraint failed".

    Esta copiada de 8f3c1d02b7a4, d4a2b6f19c73 y las que la imitan por la misma
    razon que ellas la duplican: una migracion es una foto de un momento y
    tiene que poder correr sola.

    En MySQL no hace falta: ahi el batch es un ALTER TABLE comun.
    """
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        yield
        return

    bind.exec_driver_sql('PRAGMA foreign_keys=OFF')

    # El OFF se relee: en SQLite un PRAGMA es un no-op SILENCIOSO si ya hay una
    # transaccion abierta, y sin este chequeo el sintoma aparece recien despues,
    # como un error de FK sobre un DROP que no explica nada.
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


def _abortar_si_hay_precios_invalidos(bind, tabla, condicion):
    """Un CHECK no se puede crear si ya hay filas que lo violan.

    Preferimos cortar con un mensaje que diga cuales son, antes que dejar que
    el motor tire un error a mitad de la migracion sin decir de que fila habla.
    """
    filas = bind.execute(
        sa.text(f"SELECT id FROM {tabla} WHERE NOT ({condicion})")
    ).fetchall()
    if filas:
        ids = ", ".join(str(fila[0]) for fila in filas)
        raise RuntimeError(
            f"No se puede aplicar la migracion: la tabla '{tabla}' tiene "
            f"fila(s) que no cumplen '{condicion}' (id: {ids}). "
            f"Corregi o elimina esos registros y volve a correr "
            f"'flask db upgrade'."
        )


def upgrade():
    with _sin_foreign_keys_en_sqlite():
        bind = op.get_bind()
        tablas = set(sa.inspect(bind).get_table_names())

        for tabla, nombre, condicion in CHECKS:
            # La tabla puede no existir en una base que todavia no llego hasta
            # aca por create_all; el resto de las migraciones del proyecto
            # chequea igual.
            if tabla not in tablas:
                continue
            _abortar_si_hay_precios_invalidos(bind, tabla, condicion)
            with op.batch_alter_table(tabla) as batch:
                batch.create_check_constraint(nombre, condicion)


def downgrade():
    with _sin_foreign_keys_en_sqlite():
        bind = op.get_bind()
        tablas = set(sa.inspect(bind).get_table_names())

        # batch_alter_table y no un op.drop_constraint suelto, por lo mismo que
        # en el upgrade: en SQLite no hay ALTER de constraints y hay que
        # recrear la tabla. Un `recreate='always'` vacio NO alcanzaria para
        # sacarlos: SQLAlchemy si refleja los CHECK de SQLite, asi que la copia
        # se los vuelve a llevar puestos y el downgrade quedaria en no-op.
        for tabla, nombre, _ in CHECKS:
            if tabla not in tablas:
                continue
            with op.batch_alter_table(tabla) as batch:
                batch.drop_constraint(nombre, type_='check')
