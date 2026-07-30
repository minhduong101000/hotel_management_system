from sqlalchemy import func, inspect, or_

from extensions import db
from models import Booking, BookingRoom, Payment, Room
from models.expense import Expense
from models.inventory_batch import InventoryBatch
from models.inventory_movement import InventoryMovement
from services.reconciliation.common import issue


def reconcile_tenant_links(hotel_id, *, apply):
    del apply
    issues = []

    booking_rooms = (
        BookingRoom.query.outerjoin(
            Booking,
            Booking.id == BookingRoom.booking_id,
        )
        .outerjoin(Room, Room.id == BookingRoom.room_id)
        .filter(
            or_(
                BookingRoom.hotel_id == hotel_id,
                Booking.hotel_id == hotel_id,
                Room.hotel_id == hotel_id,
            )
        )
        .order_by(BookingRoom.id)
        .all()
    )
    for booking_room in booking_rooms:
        if (
            booking_room.booking is None
            or booking_room.room is None
            or booking_room.hotel_id != booking_room.booking.hotel_id
            or booking_room.hotel_id != booking_room.room.hotel_id
        ):
            issues.append(
                issue(
                    rule="tenant_link",
                    entity_type="booking_room",
                    entity_id=booking_room.id,
                    current="missing_or_mismatch",
                    expected="same_tenant",
                )
            )

    payments = (
        Payment.query.outerjoin(Booking, Booking.id == Payment.booking_id)
        .filter(
            or_(
                Payment.hotel_id == hotel_id,
                Booking.hotel_id == hotel_id,
            )
        )
        .order_by(Payment.id)
        .all()
    )
    for payment in payments:
        if (
            payment.booking is None
            or payment.hotel_id != payment.booking.hotel_id
        ):
            issues.append(
                issue(
                    rule="tenant_link",
                    entity_type="payment",
                    entity_id=payment.id,
                    current="missing_or_mismatch",
                    expected="same_tenant",
                )
            )

    batches = (
        InventoryBatch.query.outerjoin(
            Expense,
            Expense.id == InventoryBatch.expense_id,
        )
        .filter(
            or_(
                InventoryBatch.hotel_id == hotel_id,
                Expense.hotel_id == hotel_id,
            )
        )
        .all()
    )
    movements = (
        InventoryMovement.query.outerjoin(
            Expense,
            Expense.id == InventoryMovement.expense_id,
        )
        .filter(
            or_(
                InventoryMovement.hotel_id == hotel_id,
                Expense.hotel_id == hotel_id,
            )
        )
        .all()
    )
    for linked_row in [*batches, *movements]:
        if (
            linked_row.expense is None
            or linked_row.hotel_id != linked_row.expense.hotel_id
        ):
            issues.append(
                issue(
                    rule="tenant_link",
                    entity_type=linked_row.__class__.__tablename__,
                    entity_id=linked_row.id,
                    current="expense_mismatch",
                    expected="same_tenant",
                )
            )
    return issues


def reconcile_room_number_constraint(hotel_id, *, apply):
    del apply
    issues = []
    duplicates = (
        db.session.query(Room.room_number, func.count(Room.id))
        .filter(Room.hotel_id == hotel_id)
        .group_by(Room.room_number)
        .having(func.count(Room.id) > 1)
        .all()
    )
    for room_number, count in duplicates:
        issues.append(
            issue(
                rule="room_number_duplicate",
                entity_type="room",
                entity_id=None,
                current=int(count),
                expected=1,
                note=f"Số phòng trùng: {room_number}",
            )
        )

    constraints = inspect(
        db.session.connection()
    ).get_unique_constraints("rooms")
    has_constraint = any(
        set(constraint.get("column_names") or [])
        == {"hotel_id", "room_number"}
        for constraint in constraints
    )
    if not has_constraint:
        issues.append(
            issue(
                rule="room_constraint",
                entity_type="schema",
                entity_id=None,
                current="missing",
                expected="unique(hotel_id, room_number)",
            )
        )
    return issues
