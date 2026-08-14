"""Add payments.created_by to track which staff member handled money.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "payments",
        sa.Column("created_by", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_payments_created_by_user",
        "payments",
        "users",
        ["created_by"],
        ["id"],
    )


def downgrade():
    op.drop_constraint(
        "fk_payments_created_by_user", "payments", type_="foreignkey"
    )
    op.drop_column("payments", "created_by")
