"""Agregar horarios de atencion

Revision ID: e5b71c92a840
Revises: c8a4f1e07d36
Create Date: 2026-08-14 15:45:00.000000

Un rango de apertura/cierre por dia de la semana, en hora local de Argentina.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5b71c92a840'
down_revision = 'c8a4f1e07d36'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'horarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('dia_semana', sa.Integer(), nullable=False),
        sa.Column('abre', sa.Time(), nullable=True),
        sa.Column('cierra', sa.Time(), nullable=True),
        sa.Column('cerrado', sa.Boolean(), nullable=False, server_default='0'),
        # CASCADE explicito: en MySQL el default es RESTRICT y borrar un
        # usuario con horarios cargados fallaria con IntegrityError.
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'dia_semana', name='uq_horario_user_dia'),
    )
    with op.batch_alter_table('horarios', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_horarios_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('horarios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_horarios_user_id'))
    op.drop_table('horarios')
