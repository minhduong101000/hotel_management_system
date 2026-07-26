"""Add idempotent business operations.

Revision ID: c2f6a7d8e9b0
Revises: a3471c834318
Create Date: 2026-07-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'c2f6a7d8e9b0'
down_revision = 'a3471c834318'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'business_operations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('hotel_id', sa.Integer(), nullable=False),
        sa.Column('operation_key', sa.String(length=120), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['hotel_id'], ['hotels.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('hotel_id', 'operation_key', name='_hotel_operation_key_uc'),
    )
    op.create_index(
        'ix_business_operations_hotel_entity',
        'business_operations',
        ['hotel_id', 'entity_type', 'entity_id'],
        unique=False,
    )


def downgrade():
    op.drop_index('ix_business_operations_hotel_entity', table_name='business_operations')
    op.drop_table('business_operations')
