"""Add audit events.

Revision ID: d3e7f8a9b0c1
Revises: c2f6a7d8e9b0
Create Date: 2026-07-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'd3e7f8a9b0c1'
down_revision = 'c2f6a7d8e9b0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'audit_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('hotel_id', sa.Integer(), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=80), nullable=False),
        sa.Column('entity_type', sa.String(length=80), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('operation_key', sa.String(length=120), nullable=True),
        sa.Column('before_data', sa.JSON(), nullable=True),
        sa.Column('after_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['hotel_id'], ['hotels.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_events_hotel_created', 'audit_events', ['hotel_id', 'created_at'])
    op.create_index('ix_audit_events_hotel_entity', 'audit_events', ['hotel_id', 'entity_type', 'entity_id'])


def downgrade():
    op.drop_index('ix_audit_events_hotel_entity', table_name='audit_events')
    op.drop_index('ix_audit_events_hotel_created', table_name='audit_events')
    op.drop_table('audit_events')
