"""Agregar galeria de fotos por emprendimiento

Revision ID: c8a4f1e07d36
Revises: b7e2d05c1943
Create Date: 2026-08-14 15:10:00.000000

La foto principal sigue en posts.image; esta tabla guarda las adicionales.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8a4f1e07d36'
down_revision = 'b7e2d05c1943'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'post_images',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=100), nullable=False),
        sa.Column('posicion', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created', sa.DateTime(), nullable=False),
        # ondelete='CASCADE' explicito: sin esto MySQL usa RESTRICT y borrar un
        # emprendimiento con fotos falla con IntegrityError, el mismo bug que
        # ya se arreglo en reports (d09128dd029c) y en favorites/messages
        # (b30b4ba8d199).
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('post_images', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_post_images_post_id'), ['post_id'], unique=False)


def downgrade():
    with op.batch_alter_table('post_images', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_post_images_post_id'))
    op.drop_table('post_images')
