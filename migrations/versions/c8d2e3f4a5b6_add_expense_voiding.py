"""Add expense voiding audit fields.

Revision ID: c8d2e3f4a5b6
Revises: b7c1d2e3f4a5
"""
from alembic import op
import sqlalchemy as sa

revision = 'c8d2e3f4a5b6'
down_revision = 'b7c1d2e3f4a5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('expenses', sa.Column('is_voided', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('expenses', sa.Column('void_reason', sa.String(length=255), nullable=True))
    op.add_column('expenses', sa.Column('voided_at', sa.DateTime(), nullable=True))
    op.add_column('expenses', sa.Column('voided_by', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_expenses_voided_by_users', 'expenses', 'users', ['voided_by'], ['id'])


def downgrade():
    op.drop_constraint('fk_expenses_voided_by_users', 'expenses', type_='foreignkey')
    op.drop_column('expenses', 'voided_by')
    op.drop_column('expenses', 'voided_at')
    op.drop_column('expenses', 'void_reason')
    op.drop_column('expenses', 'is_voided')
