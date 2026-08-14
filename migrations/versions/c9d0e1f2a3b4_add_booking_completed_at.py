"""Add bookings.completed_at with backfill from room checkouts.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-08-14

Backfill: booking đã completed lấy MAX(booking_rooms.check_out_actual).
Bản ghi không suy ra được mốc giữ NULL (reconciliation nhận diện sau),
tuyệt đối không bịa từ updated_at.
"""

from alembic import op
import sqlalchemy as sa


revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "bookings",
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        """
        UPDATE bookings
        SET completed_at = (
            SELECT MAX(booking_rooms.check_out_actual)
            FROM booking_rooms
            WHERE booking_rooms.booking_id = bookings.id
        )
        WHERE bookings.status = 'completed'
        """
    )


def downgrade():
    op.drop_column("bookings", "completed_at")
