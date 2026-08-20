"""Agregar verificacion de credenciales de un servicio

Revision ID: a2f7c50e19bd
Revises: d7a1c58b3e94
Create Date: 2026-08-18 15:40:00.000000

El prestador sube la foto de su matricula o certificado para un servicio
puntual, un admin la revisa, y si la aprueba el servicio queda marcado como
verificado en la busqueda publica.

Dos cosas: la columna services.verificado (la que mira el visitante) y la tabla
verification_requests (la cola que mira el admin). Van juntas en una sola
migracion porque una sin la otra no significa nada: el flag sin la cola no lo
puede escribir nadie, y la cola sin el flag no tiene donde dejar el resultado.

services.verificado nace en 0 para todas las filas existentes, que es lo
correcto: nadie reviso ninguna todavia.

verification_requests lleva la columna centinela cupo_pendiente y su UNIQUE
desde el principio, y no en una migracion de correccion posterior como paso con
service_requests (c5e91a70d3f8) y reports (d7a1c58b3e94). Por eso aca no hay
nada que limpiar antes de crear la constraint: la tabla nace vacia, sin
duplicados posibles.
"""
from contextlib import contextmanager

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a2f7c50e19bd'
down_revision = 'd7a1c58b3e94'
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
    # batch_alter_table para que tambien funcione en SQLite, que no soporta
    # ALTER de columnas (es lo que usan los tests).
    with op.batch_alter_table('services', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'verificado', sa.Boolean(), nullable=False, server_default='0'))

    op.create_table(
        'verification_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('service_id', sa.Integer(), nullable=False),
        sa.Column('foto', sa.String(length=100), nullable=True),
        sa.Column('estado', sa.String(length=20), nullable=False,
                  server_default='pendiente'),
        sa.Column('cupo_pendiente', sa.Integer(), nullable=True),
        sa.Column('motivo_rechazo', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('resuelto_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='CASCADE',
                                name='fk_verification_requests_service_id_services'),
        sa.PrimaryKeyConstraint('id'),
        # Ver el docstring de app/servicios/modelo_verificacion.py: sin la
        # columna centinela no hay constraint posible, porque UNIQUE(service_id)
        # a secas prohibiria para siempre un segundo pedido despues de un
        # rechazo. Con ella, el UNIQUE solo compara las pendientes (los dos
        # motores eximen a las filas con NULL).
        sa.UniqueConstraint('service_id', 'cupo_pendiente',
                            name='uq_verification_requests_pendiente'),
    )
    with op.batch_alter_table('verification_requests', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_verification_requests_service_id'),
            ['service_id'], unique=False)
        # El panel del admin filtra por estado, y el listado ordena por fecha.
        batch_op.create_index(
            batch_op.f('ix_verification_requests_estado'), ['estado'], unique=False)
        batch_op.create_index(
            batch_op.f('ix_verification_requests_created_at'),
            ['created_at'], unique=False)


def downgrade():
    with _sin_foreign_keys_en_sqlite():
        # La tabla primero y la columna despues: al reves no importa (no hay FK
        # entre las dos), pero deshace en el orden inverso al upgrade, que es como
        # se lee sin tener que pensarlo.
        #
        # Solo drop_table, sin dropear los indices antes: el de la FK la sostiene y
        # MySQL no lo deja sacar mientras la FK exista. Dropear la tabla se lleva
        # sus indices igual, en los dos motores.
        op.drop_table('verification_requests')

        # Se pierde que servicios estaban verificados. No hay donde guardarlo: la
        # tabla que tenia el historial se acaba de borrar, y es justamente lo que
        # pide un downgrade de esta migracion.
        with op.batch_alter_table('services', schema=None) as batch_op:
            batch_op.drop_column('verificado')
