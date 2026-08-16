"""Una sola solicitud pendiente por cliente y servicio

Revision ID: c5e91a70d3f8
Revises: f3b48d10a7c5
Create Date: 2026-08-16 21:05:00.000000

El freno de "una sola pendiente" estaba solo en la vista, que chequea con un
SELECT y despues inserta. Entre esas dos cosas hay una ventana: dos requests
que entran juntos (el doble click que manda dos POST, dos pestañas) pasan los
dos el chequeo y guardan los dos. Lo unico que cierra esa ventana es una
constraint en la base.

MySQL no tiene unique parcial (el "WHERE estado = 'pendiente'" de Postgres), asi
que la regla se escribe con una columna auxiliar: cupo_pendiente vale 1 mientras
la solicitud esta pendiente y NULL cuando no lo esta, y el UNIQUE es sobre
(service_id, cliente_id, cupo_pendiente). Los dos motores ignoran las filas con
NULL en un UNIQUE, asi que solo quedan comparadas las pendientes. La columna la
mantiene un listener del modelo (ver app/servicios/modelo_solicitud.py).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5e91a70d3f8'
down_revision = 'f3b48d10a7c5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('service_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cupo_pendiente', sa.Integer(), nullable=True))

    conexion = op.get_bind()

    # Si la base ya tiene duplicados (son justamente los que dejo pasar el bug),
    # el UNIQUE no se puede crear. Se conserva la de id mas chico de cada grupo
    # y las demas se cierran: no se borran porque pueden tener una foto y un
    # texto que el cliente escribio, y "cerrada" ya significa "archivada, no
    # hace falta contestarla".
    #
    # El criterio es MIN(id) y no MIN(created_at) a proposito, y no son lo mismo:
    # el id lo pone la base al insertar, asi que siempre marca cual entro
    # primero, mientras que created_at se puede escribir con cualquier fecha
    # (scripts/seed.py, sin ir mas lejos, backdatea las solicitudes que carga).
    # Para el caso que importa aca -- dos requests que se pisaron -- el que entro
    # primero es el que el cliente vio y el que el prestador tiene en su lista.
    #
    # El SELECT anidado va envuelto en una subconsulta con alias porque MySQL no
    # deja leer en un UPDATE la misma tabla que esta actualizando si no hay una
    # tabla derivada de por medio. En SQLite funciona igual.
    conexion.execute(sa.text("""
        UPDATE service_requests
           SET estado = 'cerrada'
         WHERE estado = 'pendiente'
           AND id NOT IN (
               SELECT id FROM (
                   SELECT MIN(id) AS id
                     FROM service_requests
                    WHERE estado = 'pendiente'
                    GROUP BY service_id, cliente_id
               ) AS primeras
           )
    """))

    conexion.execute(sa.text(
        "UPDATE service_requests SET cupo_pendiente = 1 WHERE estado = 'pendiente'"
    ))

    # batch_alter_table para que tambien funcione en SQLite, que no soporta
    # ALTER de constraints (es lo que usan los tests).
    with op.batch_alter_table('service_requests', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            'uq_service_requests_pendiente',
            ['service_id', 'cliente_id', 'cupo_pendiente'],
        )


def downgrade():
    # Las solicitudes que esta migracion cerro por duplicadas no vuelven a
    # pendiente: no hay forma de distinguirlas de las que se cerraron de verdad.
    with op.batch_alter_table('service_requests', schema=None) as batch_op:
        batch_op.drop_constraint('uq_service_requests_pendiente', type_='unique')
        batch_op.drop_column('cupo_pendiente')
