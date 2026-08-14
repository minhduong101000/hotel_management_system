"""Add refund reversal linkage to payments.

Revision ID: b8c9d0e1f2a3
Revises: a2b3c4d5e6f7
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "b8c9d0e1f2a3"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "payments",
        sa.Column("reverses_payment_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_payments_reverses_payment",
        "payments",
        "payments",
        ["reverses_payment_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_payments_reverses_once",
        "payments",
        ["reverses_payment_id"],
    )


def downgrade():
    # MySQL: phải bỏ FK trước — unique index đang được FK sử dụng (lỗi 1553)
    op.drop_constraint(
        "fk_payments_reverses_payment", "payments", type_="foreignkey"
    )
    op.drop_constraint("uq_payments_reverses_once", "payments", type_="unique")
    op.drop_column("payments", "reverses_payment_id")
