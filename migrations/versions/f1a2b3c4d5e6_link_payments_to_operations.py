"""Link payments to business operations.

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-07-30
"""

from alembic import context, op
import sqlalchemy as sa


revision = "f1a2b3c4d5e6"
down_revision = "e0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "business_operations",
        sa.Column("request_fingerprint", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "business_operations",
        sa.Column("result_snapshot", sa.JSON(), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column("business_operation_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column("component_key", sa.String(length=120), nullable=True),
    )
    op.create_foreign_key(
        "fk_payments_business_operation",
        "payments",
        "business_operations",
        ["business_operation_id"],
        ["id"],
    )
    if context.is_offline_mode():
        op.create_index(
            "ix_payments_hotel_booking",
            "payments",
            ["hotel_id", "booking_id"],
            unique=False,
        )
    else:
        existing_indexes = {
            index["name"]
            for index in sa.inspect(op.get_bind()).get_indexes("payments")
        }
        if "ix_payments_hotel_booking" not in existing_indexes:
            op.create_index(
                "ix_payments_hotel_booking",
                "payments",
                ["hotel_id", "booking_id"],
                unique=False,
            )
    op.create_unique_constraint(
        "uq_payments_operation_component",
        "payments",
        ["hotel_id", "business_operation_id", "component_key"],
    )


def downgrade():
    op.drop_constraint(
        "fk_payments_business_operation",
        "payments",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_payments_operation_component",
        "payments",
        type_="unique",
    )
    op.drop_column("payments", "component_key")
    op.drop_column("payments", "business_operation_id")
    op.drop_column("business_operations", "result_snapshot")
    op.drop_column("business_operations", "request_fingerprint")
