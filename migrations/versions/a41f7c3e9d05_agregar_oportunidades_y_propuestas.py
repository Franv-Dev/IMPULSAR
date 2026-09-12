"""Agregar oportunidades y propuestas

Revision ID: a41f7c3e9d05
Revises: 88a6ceb0bb22
Create Date: 2026-09-11 20:31:14.208377

Cualquier usuario con el perfil completo publica que necesita un servicio, y
los emprendimientos le mandan propuestas con precio y plazo. Dos tablas:

  oportunidades   la necesidad publicada, con su estado
  propuestas      lo que ofrece cada emprendimiento, colgado de la oportunidad

ES LA PRIMERA TABLA DEL PROYECTO QUE NO CUELGA DE UN POST: oportunidades.autor_id
apunta a users. Las propuestas si cuelgan de un post, porque quien ofrece es un
emprendimiento y no una persona -- de ahi la asimetria de permisos del dominio.

UNIQUE(oportunidad_id, cupo_aceptada) es el unique parcial portable, el mismo
que service_requests.cupo_pendiente y busquedas_personal.cupo_activa:
cupo_aceptada vale 1 mientras esa propuesta esta aceptada y NULL cuando no, y
como los dos motores ignoran los NULL en un UNIQUE, la regla termina siendo
"una sola propuesta aceptada por oportunidad" sin impedir que haya todas las
demas que hagan falta. Lo que tapa es el doble click en "Aceptar", que si no
deja a dos emprendedores convencidos de que ganaron.

NO hay unique (oportunidad_id, post_id), al reves que postulaciones: un
emprendimiento puede mandar varias propuestas a la misma oportunidad a
proposito, porque la segunda (despues de hablar por chat) es informacion nueva
y no un duplicado.

Los textos son String(n) y no Text aunque sean parrafos: sobre los tres corre
validar_largo, y largo_de() sobre una columna Text devuelve None (H4).

plazo_dias es un entero de dias y no texto libre: la pantalla del publicador
tiene que comparar propuestas, y "2 semanas", "15 dias" y "quincena" no se
comparan. El CHECK acota el rango a lo que tiene sentido.

Las tres FK nacen con ON DELETE CASCADE, que desde b2b97d078fb2 es la regla del
proyecto.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a41f7c3e9d05'
down_revision = '88a6ceb0bb22'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('oportunidades',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('autor_id', sa.Integer(), nullable=False),
    sa.Column('titulo', sa.String(length=120), nullable=False),
    sa.Column('descripcion', sa.String(length=800), nullable=False),
    sa.Column('presupuesto', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('fecha_limite', sa.Date(), nullable=True),
    sa.Column('estado', sa.String(length=20), server_default='abierta', nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('cerrada_at', sa.DateTime(), nullable=True),
    sa.Column('finalizada_at', sa.DateTime(), nullable=True),
    sa.CheckConstraint('presupuesto IS NULL OR presupuesto > 0', name='ck_oportunidades_presupuesto_positivo'),
    sa.ForeignKeyConstraint(['autor_id'], ['users.id'], name='fk_oportunidades_autor_id_users', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('oportunidades', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_oportunidades_autor_id'), ['autor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_oportunidades_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_oportunidades_estado'), ['estado'], unique=False)

    op.create_table('propuestas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('oportunidad_id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('precio', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('plazo_dias', sa.Integer(), nullable=False),
    sa.Column('mensaje', sa.String(length=600), nullable=False),
    sa.Column('aceptada', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('cupo_aceptada', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint('plazo_dias > 0 AND plazo_dias <= 365', name='ck_propuestas_plazo_razonable'),
    sa.CheckConstraint('precio > 0', name='ck_propuestas_precio_positivo'),
    sa.ForeignKeyConstraint(['oportunidad_id'], ['oportunidades.id'], name='fk_propuestas_oportunidad_id_oportunidades', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], name='fk_propuestas_post_id_posts', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('oportunidad_id', 'cupo_aceptada', name='uq_propuestas_aceptada')
    )
    with op.batch_alter_table('propuestas', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_propuestas_aceptada'), ['aceptada'], unique=False)
        batch_op.create_index(batch_op.f('ix_propuestas_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_propuestas_oportunidad_id'), ['oportunidad_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_propuestas_post_id'), ['post_id'], unique=False)


def downgrade():
    """Borra las dos tablas, y SOLO las tablas.

    Sin los drop_index que escribe el autogenerate, a proposito y no por
    descuido: en MySQL un DROP INDEX sobre la columna de una foreign key falla
    con el error 1553 ("needed in a foreign key constraint"), asi que el
    downgrade autogenerado muere en la primera linea contra el motor de
    produccion -- se comprobo en una base descartable. En SQLite pasa, que es
    por lo que esto se cuela sin que los tests digan nada.

    Y no hacen falta: DROP TABLE se lleva los indices de la tabla en los dos
    motores. El orden si importa, propuestas antes que oportunidades, porque la
    FK apunta para ese lado.
    """
    op.drop_table('propuestas')
    op.drop_table('oportunidades')
