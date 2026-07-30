"""Scope room numbers by hotel.

Revision ID: e0f1a2b3c4d5
Revises: d9e3f4a5b6c7
Create Date: 2026-07-30
"""

from alembic import context, op
import sqlalchemy as sa


revision = "e0f1a2b3c4d5"
down_revision = "d9e3f4a5b6c7"
branch_labels = None
depends_on = None

TENANT_CONSTRAINT = "uq_rooms_hotel_room_number"


def _duplicate_rows(group_columns):
    bind = op.get_bind()
    columns_sql = ", ".join(group_columns)
    return bind.execute(
        sa.text(
            f"SELECT {columns_sql}, COUNT(*) AS duplicate_count "
            "FROM rooms "
            f"GROUP BY {columns_sql} "
            "HAVING COUNT(*) > 1 "
            "LIMIT 10"
        )
    ).mappings().all()


def _format_duplicates(rows, keys):
    return ", ".join(
        "/".join(str(row[key]) for key in keys)
        + f" ({row['duplicate_count']} bản ghi)"
        for row in rows
    )


def _drop_global_room_number_uniqueness():
    inspector = sa.inspect(op.get_bind())
    dropped_names = set()

    for constraint in inspector.get_unique_constraints("rooms"):
        if constraint.get("column_names") == ["room_number"]:
            op.drop_constraint(constraint["name"], "rooms", type_="unique")
            dropped_names.add(constraint["name"])

    for index in inspector.get_indexes("rooms"):
        if (
            index.get("unique")
            and index.get("column_names") == ["room_number"]
            and index["name"] not in dropped_names
        ):
            op.drop_index(index["name"], table_name="rooms")


def upgrade():
    if context.is_offline_mode():
        op.drop_constraint("room_number", "rooms", type_="unique")
        op.create_unique_constraint(
            TENANT_CONSTRAINT,
            "rooms",
            ["hotel_id", "room_number"],
        )
        return

    duplicates = _duplicate_rows(["hotel_id", "room_number"])
    if duplicates:
        details = _format_duplicates(duplicates, ["hotel_id", "room_number"])
        raise RuntimeError(
            "Không thể áp dụng unique theo khách sạn vì có trùng số phòng: "
            f"{details}. Hãy xử lý dữ liệu trùng rồi chạy migration lại."
        )

    _drop_global_room_number_uniqueness()
    op.create_unique_constraint(
        TENANT_CONSTRAINT,
        "rooms",
        ["hotel_id", "room_number"],
    )


def downgrade():
    if context.is_offline_mode():
        op.drop_constraint(TENANT_CONSTRAINT, "rooms", type_="unique")
        op.create_unique_constraint("room_number", "rooms", ["room_number"])
        return

    duplicates = _duplicate_rows(["room_number"])
    if duplicates:
        details = _format_duplicates(duplicates, ["room_number"])
        raise RuntimeError(
            "Không thể quay lại unique số phòng toàn hệ thống vì các khách sạn "
            f"đang dùng trùng số phòng: {details}."
        )

    op.drop_constraint(TENANT_CONSTRAINT, "rooms", type_="unique")
    op.create_unique_constraint("room_number", "rooms", ["room_number"])
