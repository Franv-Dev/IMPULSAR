"""Un solo reporte pendiente por usuario y objetivo

Revision ID: d7a1c58b3e94
Revises: c5e91a70d3f8
Create Date: 2026-08-18 10:40:00.000000

El freno de "un solo reporte pendiente" estaba solo en la vista, que chequea con
un SELECT y despues inserta. Entre esas dos cosas hay una ventana: dos requests
que entran juntos (el doble click que manda dos POST, dos pestañas) pasan los
dos el chequeo y guardan los dos. Lo unico que cierra esa ventana es una
constraint en la base.

El UNIQUE natural, (reporter_id, post_id, review_id, <lo que marque pendiente>),
no sirve: post_id y review_id son excluyentes, asi que cualquier tupla que los
incluya lleva siempre un NULL, y los dos motores eximen del UNIQUE a las filas
con NULL. La constraint existiria y no frenaria nada.

Por eso la columna centinela: clave_pendiente colapsa las dos FK en un valor
solo ('p<post_id>' o 'r<review_id>') mientras el reporte esta sin resolver, y
NULL cuando se resuelve. El UNIQUE es (reporter_id, clave_pendiente), y ahi el
NULL pasa a ser deliberado: exime a los resueltos, que si pueden repetirse. La
columna la mantiene un listener del modelo (ver app/blog/modelo_reporte.py).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd7a1c58b3e94'
down_revision = 'c5e91a70d3f8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('clave_pendiente', sa.String(length=32), nullable=True))

    conexion = op.get_bind()

    # Si la base ya tiene duplicados (son justamente los que dejo pasar el bug),
    # el UNIQUE no se puede crear. Se conserva el de id mas chico de cada grupo
    # y los demas se dan por resueltos: no se borran porque el texto del motivo
    # es lo que el usuario escribio, y "resuelto" ya significa "el admin no lo
    # tiene que mirar", que es exactamente lo que pasa cuando el mismo usuario
    # reporto dos veces lo mismo.
    #
    # El criterio es MIN(id) y no MIN(created) a proposito, y no son lo mismo:
    # el id lo pone la base al insertar, asi que siempre marca cual entro
    # primero, mientras que created se puede escribir con cualquier fecha
    # (scripts/seed.py backdatea lo que carga). El que entro primero es el que
    # el admin ya tiene en su lista.
    #
    # resolved_at queda en NULL en los que se cierran aca: no se sabe cuando se
    # resolvieron porque no se resolvieron, se archivaron. El panel de admin lo
    # muestra vacio, que es mas honesto que inventar una fecha.
    #
    # COALESCE porque post_id y review_id son excluyentes: agrupar por los dos
    # con NULL de por medio no junta nada en MySQL. El prefijo 'p'/'r' evita que
    # el post 7 y la resenia 7 caigan en el mismo grupo.
    #
    # El SELECT anidado va envuelto en una subconsulta con alias porque MySQL no
    # deja leer en un UPDATE la misma tabla que esta actualizando si no hay una
    # tabla derivada de por medio. En SQLite funciona igual.
    conexion.execute(sa.text("""
        UPDATE reports
           SET resolved = 1
         WHERE resolved = 0
           AND id NOT IN (
               SELECT id FROM (
                   SELECT MIN(id) AS id
                     FROM reports
                    WHERE resolved = 0
                    GROUP BY reporter_id,
                             COALESCE('p' || post_id, 'r' || review_id)
               ) AS primeros
           )
    """) if conexion.dialect.name == "sqlite" else sa.text("""
        UPDATE reports
           SET resolved = 1
         WHERE resolved = 0
           AND id NOT IN (
               SELECT id FROM (
                   SELECT MIN(id) AS id
                     FROM reports
                    WHERE resolved = 0
                    GROUP BY reporter_id,
                             COALESCE(CONCAT('p', post_id), CONCAT('r', review_id))
               ) AS primeros
           )
    """))

    # Los que quedaron pendientes estrenan la clave. Mismo COALESCE por dialecto:
    # SQLite concatena con || y MySQL con CONCAT().
    conexion.execute(sa.text(
        "UPDATE reports SET clave_pendiente = COALESCE('p' || post_id, 'r' || review_id)"
        " WHERE resolved = 0"
    ) if conexion.dialect.name == "sqlite" else sa.text(
        "UPDATE reports SET clave_pendiente ="
        " COALESCE(CONCAT('p', post_id), CONCAT('r', review_id))"
        " WHERE resolved = 0"
    ))

    # batch_alter_table para que tambien funcione en SQLite, que no soporta
    # ALTER de constraints (es lo que usan los tests).
    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            'uq_reports_pendiente',
            ['reporter_id', 'clave_pendiente'],
        )


def downgrade():
    # Los reportes que esta migracion dio por resueltos no vuelven a pendientes:
    # no hay forma de distinguirlos de los que el admin resolvio de verdad.
    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.drop_constraint('uq_reports_pendiente', type_='unique')
        batch_op.drop_column('clave_pendiente')
