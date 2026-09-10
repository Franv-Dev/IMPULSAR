"""CHECK de horarios coherentes

Revision ID: b6d29e4f1a83
Revises: a4e18c37d9b2
Create Date: 2026-09-02

Dos reglas sobre horarios, y una tercera que NO se puede escribir.

La que no se puede: "abre < cierra". Un bar de 20:00 a 02:00 cierra al dia
siguiente, y ese cruce de medianoche lo contemplan tanto
services/horarios.esta_abierto() como el filtro "Abierto ahora" del listado.
Un CHECK de abre < cierra rechazaria todos los horarios nocturnos, que son
validos y bastante comunes justo en los rubros que mas los usan.

Las que si valen, cruce o no:

  ck_horarios_abre_distinto_de_cierra
      abre <> cierra. "De 09:00 a 09:00" no se puede leer (¿cerrado siempre o
      abierto las 24 horas?) y los dos lectores del horario lo toman como
      cerrado, sin avisar. Con una hora en NULL la comparacion da desconocido y
      el CHECK pasa, que es lo correcto: de eso se ocupa el otro.

  ck_horarios_dia_abierto_con_horas
      cerrado <> 0 OR (abre IS NOT NULL AND cierra IS NOT NULL). Un dia abierto
      tiene las dos horas. Ya lo garantiza en cada escritura
      app/perfil/reglas.horario_del_dia (un dia sin horas se guarda como
      cerrado), asi que una fila a medio cargar no sale de la app.

Sin pragma de FK a diferencia de las otras migraciones con batch: horarios no
es una tabla referenciada (nadie tiene una FK a ella), asi que recrearla en
SQLite no puede romper ninguna. La FK propia a users se copia con la tabla.

MySQL viejo: el segundo es un CHECK con condicion y recien se valida desde
8.0.16; el primero es una comparacion llana, pero MySQL anterior a esa version
igual ignora todos los CHECK. Es el mismo limite que ya anota
Service.duracion_turno_minutos.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b6d29e4f1a83'
down_revision = 'a4e18c37d9b2'
branch_labels = None
depends_on = None


CHECKS = (
    ("ck_horarios_abre_distinto_de_cierra", "abre <> cierra"),
    ("ck_horarios_dia_abierto_con_horas",
     "cerrado <> 0 OR (abre IS NOT NULL AND cierra IS NOT NULL)"),
)


def _abortar_si_hay_horarios_invalidos(bind, condicion):
    """Un CHECK no se puede crear si ya hay filas que lo violan.

    Se corta con los ids a la vista en vez de dejar que el motor tire un error
    a mitad de la migracion sin decir de que fila habla. No se arreglan solas a
    proposito: cual es el horario que el emprendedor quiso cargar no lo sabe
    esta migracion, y elegir uno por el seria inventarle un horario de atencion
    a un negocio real.
    """
    filas = bind.execute(
        sa.text(f"SELECT id, user_id, dia_semana FROM horarios WHERE NOT ({condicion})")
    ).fetchall()
    if filas:
        detalle = ", ".join(
            f"id={fila[0]} (user_id={fila[1]}, dia={fila[2]})" for fila in filas
        )
        raise RuntimeError(
            f"No se puede aplicar la migracion: la tabla 'horarios' tiene "
            f"fila(s) que no cumplen '{condicion}': {detalle}. "
            f"Corregi o elimina esos registros y volve a correr "
            f"'flask db upgrade'."
        )


def upgrade():
    bind = op.get_bind()
    if "horarios" not in set(sa.inspect(bind).get_table_names()):
        return

    for nombre, condicion in CHECKS:
        _abortar_si_hay_horarios_invalidos(bind, condicion)
        with op.batch_alter_table("horarios") as batch:
            batch.create_check_constraint(nombre, condicion)


def downgrade():
    bind = op.get_bind()
    if "horarios" not in set(sa.inspect(bind).get_table_names()):
        return

    # Por nombre y en modo batch, igual que en a4e18c37d9b2: en SQLite no hay
    # ALTER de constraints y hay que recrear la tabla, pero recrearla y ya no
    # los sacaria, porque SQLAlchemy si refleja los CHECK de SQLite.
    for nombre, _ in CHECKS:
        with op.batch_alter_table("horarios") as batch:
            batch.drop_constraint(nombre, type_='check')
