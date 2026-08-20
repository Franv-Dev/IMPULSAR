"""Agregar sistema de seguir

Revision ID: f2c6a83d5194
Revises: e5b71c92a840
Create Date: 2026-08-14 16:20:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2c6a83d5194'
down_revision = 'e5b71c92a840'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'follows',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('follower_id', sa.Integer(), nullable=False),
        sa.Column('followed_id', sa.Integer(), nullable=False),
        sa.Column('created', sa.DateTime(), nullable=False),
        # Las dos FK con CASCADE: en MySQL el default es RESTRICT y borrar una
        # cuenta con follows fallaria con IntegrityError, el mismo bug de
        # reports (d09128dd029c) y favorites/messages (b30b4ba8d199).
        # Y las dos con nombre explicito: sin nombre cada motor le pone el suyo
        # (follows_ibfk_1/2 en MySQL, ninguno en SQLite), asi que una migracion
        # posterior que necesite dropearlas no tendria un nombre que sirva en
        # los dos, que es lo que rompio d09128dd029c (ver 22dd9d0).
        sa.ForeignKeyConstraint(['follower_id'], ['users.id'], ondelete='CASCADE',
                                name='fk_follows_follower_id_users'),
        sa.ForeignKeyConstraint(['followed_id'], ['users.id'], ondelete='CASCADE',
                                name='fk_follows_followed_id_users'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('follower_id', 'followed_id', name='uq_follow_par'),
        sa.CheckConstraint('follower_id <> followed_id', name='ck_follow_no_a_si_mismo'),
    )
    with op.batch_alter_table('follows', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_follows_follower_id'), ['follower_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_follows_followed_id'), ['followed_id'], unique=False)


def downgrade():
    # Solo drop_table: los drop_index que pone alembic solo antes fallan sobre
    # MySQL con "Cannot drop index 'ix_follows_...': needed in a foreign key
    # constraint", porque esos indices sostienen las dos FK.
    op.drop_table('follows')
