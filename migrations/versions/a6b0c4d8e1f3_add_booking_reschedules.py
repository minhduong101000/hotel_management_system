"""Add booking reschedules.

Revision ID: a6b0c4d8e1f3
Revises: f5a9b3c7d0e2
"""
from alembic import op
import sqlalchemy as sa

revision = 'a6b0c4d8e1f3'
down_revision = 'f5a9b3c7d0e2'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('booking_reschedules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('hotel_id', sa.Integer(), nullable=False), sa.Column('booking_room_id', sa.Integer(), nullable=False),
        sa.Column('old_room_id', sa.Integer(), nullable=False), sa.Column('new_room_id', sa.Integer(), nullable=False),
        sa.Column('old_check_in', sa.DateTime(), nullable=False), sa.Column('old_check_out', sa.DateTime(), nullable=False),
        sa.Column('new_check_in', sa.DateTime(), nullable=False), sa.Column('new_check_out', sa.DateTime(), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=False), sa.Column('price_mode', sa.String(length=20), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False),
    )

def downgrade():
    op.drop_table('booking_reschedules')
