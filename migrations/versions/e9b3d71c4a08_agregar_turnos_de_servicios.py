"""Agregar turnos reservables sobre un servicio

Revision ID: e9b3d71c4a08
Revises: c1f4a90b6e35
Create Date: 2026-08-25 11:20:00.000000

Tres cosas, y van juntas porque una sin las otras no significa nada: las dos
columnas de services (turnos_habilitados y duracion_turno_minutos, que son de
donde sale el corte de slots) y la tabla turnos (donde caen las reservas). El
flag sin la tabla no deja reservar nada, y la tabla sin el flag no sabe de que
servicio cortar slots ni de cuanto.

services.turnos_habilitados nace en 0 para todas las filas existentes, que es lo
correcto: nadie habilito turnos todavia. duracion_turno_minutos nace en NULL por
lo mismo, y es coherente: la columna solo significa algo con el flag prendido
(ver Service.duracion_turno_minutos).

turnos lleva la columna centinela cupo_activo y su UNIQUE desde el principio, y
no en una migracion de correccion posterior como paso con service_requests
(c5e91a70d3f8) y reports (d7a1c58b3e94). Por eso aca no hay nada que limpiar
antes de crear la constraint: la tabla nace vacia, sin duplicados posibles.

SOBRE _sin_foreign_keys_en_sqlite: el upgrade NO lo necesita y por eso no lo
usa. En SQLite un batch_alter_table solo recrea la tabla si la operacion no se
puede hacer con un ALTER nativo, y ADD COLUMN si se puede (recreate="auto" lo
resuelve solo), asi que services nunca se dropea. El downgrade si lo necesita:
ahi hay DROP COLUMN, que SQLite no tiene, el batch recrea services de verdad, y
services es una tabla referenciada: por service_requests y por
verification_requests en el momento en que se la recrea (turnos ya se dropeo un
par de lineas antes), y las dos FK estan en ON DELETE CASCADE.

Y ESO ES JUSTAMENTE EL PROBLEMA, que no es el que suena. Con PRAGMA
foreign_keys=ON -que db.py deja en toda conexion y reafirma en cada begin()- el
DROP TABLE services NO tira ningun error: en SQLite un DROP TABLE corre un
DELETE implicito, ese DELETE dispara las acciones de las FK, y como las hijas
cascadean, lo que pasa es que se vacian service_requests y verification_requests
en silencio. No hay excepcion, la migracion termina "bien", y un PRAGMA
foreign_key_check posterior da limpio, porque justamente no quedo nada
inconsistente: quedo todo borrado. El unico sintoma es el conteo de filas, y por
eso se verifica contando y no solo mirando que el downgrade no reviente.

Es exactamente el borrado mudo de service_requests que se le escapo a
a2f7c50e19bd y que solo aparecio corriendo ese downgrade aislado (ver el
docstring del listener "begin" en db.py). Apagar las FK evita el CASCADE, que es
lo que hace que las filas hijas sobrevivan a la recreacion.
"""
from contextlib import contextmanager

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9b3d71c4a08'
down_revision = 'c1f4a90b6e35'
branch_labels = None
depends_on = None


@contextmanager
def _sin_foreign_keys_en_sqlite():
    """Apaga la verificacion de FK mientras dura el batch, solo en SQLite.

    En SQLite un batch_alter_table que no puede resolverse con un ALTER nativo
    recrea la tabla: copia a una temporal, dropea la original y renombra. Aca
    hace falta en el downgrade porque services es una tabla referenciada y db.py
    deja PRAGMA foreign_keys=ON en toda conexion: con las FK prendidas, el DROP
    TABLE services no falla, VACIA a las hijas que cascadean (ver el docstring
    del modulo, que explica el sintoma y por que no se nota). Es el mismo caso
    que a2f7c50e19bd con services, d4a2b6f19c73 con posts y a3f1c9d47b52 con
    users, y esta copiada de ahi por la misma razon que se duplica _nombre_fk en
    esas: una migracion es una foto de un momento y tiene que poder correr sola.

    En MySQL no hace falta: ahi el batch es un ALTER TABLE comun, sin recrear.

    Al salir se hace detach de la conexion en vez de volver a prender el pragma:
    prenderlo no serviria de nada, porque en SQLite un PRAGMA es no-op si ya hay
    una transaccion abierta, y a esa altura el batch ya emitio DML. Por lo mismo,
    el bloque tiene que abrirse ANTES de cualquier DML de la migracion, no solo
    antes del batch que recrea.
    """
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        yield
        return

    bind.exec_driver_sql('PRAGMA foreign_keys=OFF')

    # El OFF se relee para confirmar que agarro. En SQLite un PRAGMA es un no-op
    # SILENCIOSO si ya hay una transaccion abierta: no tira error, no avisa,
    # simplemente no apaga nada. Sin este chequeo el sintoma aparece recien mas
    # adelante, como un "FOREIGN KEY constraint failed" sobre un DROP TABLE que
    # no explica por que las FK seguian prendidas.
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
    # ALTER de columnas (es lo que usan los tests). Sin apagar las FK: son dos
    # ADD COLUMN, que SQLite hace con un ALTER nativo y no recrean services (ver
    # el docstring del modulo).
    with op.batch_alter_table('services', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'turnos_habilitados', sa.Boolean(), nullable=False, server_default='0'))
        # Sin server_default: NULL es el valor correcto para las filas viejas, y
        # es lo que significa "este servicio no toma turnos".
        batch_op.add_column(sa.Column(
            'duracion_turno_minutos', sa.Integer(), nullable=True))

    op.create_table(
        'turnos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('service_id', sa.Integer(), nullable=False),
        sa.Column('cliente_id', sa.Integer(), nullable=False),
        # Date + Time y no DateTime: un turno es hora local del local, no un
        # instante en UTC (ver el docstring de app/turnos/modelo_turno.py).
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('hora_inicio', sa.Time(), nullable=False),
        sa.Column('hora_fin', sa.Time(), nullable=False),
        sa.Column('estado', sa.String(length=20), nullable=False,
                  server_default='activo'),
        sa.Column('cupo_activo', sa.Integer(), nullable=True),
        sa.Column('cancelado_por', sa.String(length=20), nullable=True),
        sa.Column('created', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='CASCADE',
                                name='fk_turnos_service_id_services'),
        sa.ForeignKeyConstraint(['cliente_id'], ['users.id'], ondelete='CASCADE',
                                name='fk_turnos_cliente_id_users'),
        sa.PrimaryKeyConstraint('id'),
        # Ver el docstring de app/turnos/modelo_turno.py: es lo unico que cierra
        # de verdad la ventana entre "esta libre?" y el INSERT. cupo_activo vale
        # 1 mientras el turno vive y NULL cuando se cancela, y los dos motores
        # eximen del UNIQUE a las filas con NULL, asi que un slot cancelado
        # vuelve a quedar reservable.
        sa.UniqueConstraint('service_id', 'fecha', 'hora_inicio', 'cupo_activo',
                            name='uq_turnos_slot_activo'),
    )
    with op.batch_alter_table('turnos', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_turnos_service_id'), ['service_id'], unique=False)
        batch_op.create_index(
            batch_op.f('ix_turnos_cliente_id'), ['cliente_id'], unique=False)
        # Toda consulta de turnos filtra por dia: la agenda del vendedor, "mis
        # turnos" del cliente y el corte de slots de una fecha.
        batch_op.create_index(batch_op.f('ix_turnos_fecha'), ['fecha'], unique=False)
        batch_op.create_index(batch_op.f('ix_turnos_estado'), ['estado'], unique=False)


def downgrade():
    # El bloque abarca TODO el downgrade y se abre antes de cualquier DML, no
    # solo alrededor del batch de services: en SQLite un PRAGMA es no-op si ya
    # hay una transaccion abierta (ver el docstring del helper).
    with _sin_foreign_keys_en_sqlite():
        # La tabla primero y las columnas despues: al reves no importa (no hay
        # FK entre las dos), pero deshace en el orden inverso al upgrade, que es
        # como se lee sin tener que pensarlo.
        #
        # Solo drop_table, sin dropear los indices antes: los de las FK las
        # sostienen y MySQL no los deja sacar mientras las FK existan. Dropear la
        # tabla se lleva sus indices igual, en los dos motores.
        op.drop_table('turnos')

        # Se pierden los turnos reservados y que servicios los tomaban. No hay
        # donde guardarlo: la tabla que tenia las reservas se acaba de borrar, y
        # es justamente lo que pide un downgrade de esta migracion.
        with op.batch_alter_table('services', schema=None) as batch_op:
            batch_op.drop_column('duracion_turno_minutos')
            batch_op.drop_column('turnos_habilitados')
