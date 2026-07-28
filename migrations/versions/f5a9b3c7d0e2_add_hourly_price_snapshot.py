"""Add hourly booking price snapshot.

Revision ID: f5a9b3c7d0e2
Revises: e4f8a2b6c9d1
"""
from alembic import op
import sqlalchemy as sa

revision = 'f5a9b3c7d0e2'
down_revision = 'e4f8a2b6c9d1'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('booking_rooms', sa.Column('hourly_price_snapshot', sa.JSON(), nullable=True))

def downgrade():
    op.drop_column('booking_rooms', 'hourly_price_snapshot')
