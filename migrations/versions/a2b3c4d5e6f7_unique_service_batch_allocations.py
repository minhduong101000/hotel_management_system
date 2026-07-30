"""Giữ một phân bổ cho mỗi dòng dịch vụ và lô hàng.

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
"""

from alembic import context, op
import sqlalchemy as sa


revision = "a2b3c4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def _merge_duplicate_allocations():
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.execute(sa.text("""
            UPDATE booking_service_batch_allocations AS target
            JOIN (
                SELECT
                    hotel_id,
                    booking_service_id,
                    batch_id,
                    MIN(id) AS keep_id,
                    SUM(quantity) AS total_quantity
                FROM booking_service_batch_allocations
                GROUP BY hotel_id, booking_service_id, batch_id
                HAVING COUNT(*) > 1
            ) AS duplicate_group
              ON target.id = duplicate_group.keep_id
            SET target.quantity = duplicate_group.total_quantity
        """))
        op.execute(sa.text("""
            DELETE duplicate_row
            FROM booking_service_batch_allocations AS duplicate_row
            JOIN (
                SELECT
                    hotel_id,
                    booking_service_id,
                    batch_id,
                    MIN(id) AS keep_id
                FROM booking_service_batch_allocations
                GROUP BY hotel_id, booking_service_id, batch_id
                HAVING COUNT(*) > 1
            ) AS duplicate_group
              ON duplicate_row.hotel_id = duplicate_group.hotel_id
             AND duplicate_row.booking_service_id =
                 duplicate_group.booking_service_id
             AND duplicate_row.batch_id = duplicate_group.batch_id
             AND duplicate_row.id <> duplicate_group.keep_id
        """))
        return

    allocation = sa.table(
        "booking_service_batch_allocations",
        sa.column("id", sa.Integer),
        sa.column("hotel_id", sa.Integer),
        sa.column("booking_service_id", sa.Integer),
        sa.column("batch_id", sa.Integer),
        sa.column("quantity", sa.Integer),
    )
    duplicates = bind.execute(
        sa.select(
            allocation.c.hotel_id,
            allocation.c.booking_service_id,
            allocation.c.batch_id,
            sa.func.min(allocation.c.id).label("keep_id"),
            sa.func.sum(allocation.c.quantity).label("total_quantity"),
        )
        .group_by(
            allocation.c.hotel_id,
            allocation.c.booking_service_id,
            allocation.c.batch_id,
        )
        .having(sa.func.count() > 1)
    ).mappings().all()
    for duplicate in duplicates:
        bind.execute(
            allocation.update()
            .where(allocation.c.id == duplicate["keep_id"])
            .values(quantity=duplicate["total_quantity"])
        )
        bind.execute(
            allocation.delete().where(
                allocation.c.hotel_id == duplicate["hotel_id"],
                allocation.c.booking_service_id
                == duplicate["booking_service_id"],
                allocation.c.batch_id == duplicate["batch_id"],
                allocation.c.id != duplicate["keep_id"],
            )
        )


def upgrade():
    _merge_duplicate_allocations()
    op.create_unique_constraint(
        "uq_booking_service_batch_allocation",
        "booking_service_batch_allocations",
        ["hotel_id", "booking_service_id", "batch_id"],
    )


def downgrade():
    op.drop_constraint(
        "uq_booking_service_batch_allocation",
        "booking_service_batch_allocations",
        type_="unique",
    )
