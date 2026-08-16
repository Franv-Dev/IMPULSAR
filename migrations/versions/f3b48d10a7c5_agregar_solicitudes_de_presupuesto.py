"""Agregar solicitudes de presupuesto

Revision ID: f3b48d10a7c5
Revises: a1c93f7e60d2
Create Date: 2026-08-16 19:20:00.000000

Un cliente pide presupuesto sobre un servicio y el prestador contesta con un
precio y un mensaje.

La FK a users nace con ON DELETE CASCADE, a diferencia de las cinco viejas
(favorites.user_id, messages.client_id, messages.sender_id, reports.reporter_id
y reviews.user_id), que no lo tienen y por eso hoy traban el borrado de un
usuario con actividad en emprendimientos ajenos. Esta tabla no repite eso.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3b48d10a7c5'
down_revision = 'a1c93f7e60d2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'service_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('service_id', sa.Integer(), nullable=False),
        sa.Column('cliente_id', sa.Integer(), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=False),
        sa.Column('zona', sa.String(length=120), nullable=True),
        sa.Column('foto', sa.String(length=100), nullable=True),
        sa.Column('estado', sa.String(length=20), nullable=False,
                  server_default='pendiente'),
        sa.Column('respuesta_precio', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('respuesta_mensaje', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='CASCADE',
                                name='fk_service_requests_service_id_services'),
        sa.ForeignKeyConstraint(['cliente_id'], ['users.id'], ondelete='CASCADE',
                                name='fk_service_requests_cliente_id_users'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('service_requests', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_service_requests_service_id'), ['service_id'], unique=False)
        batch_op.create_index(
            batch_op.f('ix_service_requests_cliente_id'), ['cliente_id'], unique=False)
        # El panel del prestador filtra por estado, y el listado ordena por
        # fecha.
        batch_op.create_index(
            batch_op.f('ix_service_requests_estado'), ['estado'], unique=False)
        batch_op.create_index(
            batch_op.f('ix_service_requests_created_at'), ['created_at'], unique=False)


def downgrade():
    # Solo drop_table, sin dropear los indices antes: los de las FK las
    # sostienen y MySQL no los deja sacar mientras las FK existan. Dropear la
    # tabla se lleva sus indices igual, en los dos motores.
    op.drop_table('service_requests')
