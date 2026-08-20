"""Agregar eventos de emprendimientos

Revision ID: a7d4e91f5c02
Revises: f2c6a83d5194
Create Date: 2026-08-14 18:20:00.000000

Eventos y ferias que un emprendimiento anuncia. La fecha es local de Argentina
(Date + Time aparte), no un instante en UTC.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7d4e91f5c02'
down_revision = 'f2c6a83d5194'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('titulo', sa.String(length=120), nullable=False),
        sa.Column('descripcion', sa.String(length=300), nullable=True),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('hora', sa.Time(), nullable=True),
        sa.Column('created', sa.DateTime(), nullable=False),
        # CASCADE explicito: en MySQL el default es RESTRICT y borrar un
        # emprendimiento con eventos cargados fallaria con IntegrityError.
        # El nombre tambien explicito: sin nombre, cada motor le pone el suyo
        # (MySQL la llamaria events_ibfk_1, SQLite no le pone ninguno), asi que
        # una migracion posterior que necesite dropearla no tendria un nombre
        # que sirva en los dos. Es lo que rompio d09128dd029c (ver 22dd9d0).
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE',
                                name='fk_events_post_id_posts'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_events_post_id'), ['post_id'], unique=False)
        # Todas las consultas de eventos filtran y ordenan por fecha.
        batch_op.create_index(batch_op.f('ix_events_fecha'), ['fecha'], unique=False)


def downgrade():
    # Solo drop_table. Los drop_index que pone alembic solo antes fallan sobre
    # MySQL con "Cannot drop index 'ix_events_post_id': needed in a foreign key
    # constraint": ese indice sostiene la FK y no se puede sacar mientras la FK
    # exista. Dropear la tabla se lleva sus indices igual, en los dos motores.
    op.drop_table('events')
