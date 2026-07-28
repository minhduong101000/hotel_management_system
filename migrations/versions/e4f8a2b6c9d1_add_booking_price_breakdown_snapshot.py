"""Add booking nightly price breakdown snapshot.

Revision ID: e4f8a2b6c9d1
Revises: d3e7f8a9b0c1
"""
from alembic import op
import sqlalchemy as sa

revision = 'e4f8a2b6c9d1'
down_revision = 'd3e7f8a9b0c1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('booking_rooms', sa.Column('price_breakdown_snapshot', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('booking_rooms', 'price_breakdown_snapshot')
