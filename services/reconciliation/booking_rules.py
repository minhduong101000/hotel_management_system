from decimal import Decimal

from models import Booking, Payment, Room
from services import booking_state_service
from services.reconciliation.common import issue, money


OPERATION_PAYMENT_TYPES = frozenset(
    {
        "room_payment",
        "service_payment",
        "tax_payment",
        "refund",
        "cancellation_fee",
        "settlement",
    }
)


def _expected_payment_status(booking):
    net_received = sum(
        (money(payment.amount) for payment in booking.payments),
        Decimal("0"),
    )
    total = money(booking.total_amount)
    if booking.status == "completed" and total == 0:
        return "paid"
    if booking.status == "cancelled" and net_received == 0:
        return "refunded"
    if net_received <= 0:
        return "unpaid"
    if total > 0 and net_received >= total:
        return "paid"
    return "partial"


def reconcile_booking_aggregates(hotel_id, *, apply):
    issues = []
    bookings = (
        Booking.query.filter_by(hotel_id=hotel_id)
        .order_by(Booking.id)
        .all()
    )
    for booking in bookings:
        rooms = list(booking.rooms)
        expected_total = sum(
            (money(room.final_amount) for room in rooms),
            Decimal("0"),
        )
        if money(booking.total_amount) != expected_total:
            issues.append(
                issue(
                    rule="booking_total",
                    entity_type="booking",
                    entity_id=booking.id,
                    current=money(booking.total_amount),
                    expected=expected_total,
                    note="Số tiền cần đối chiếu thủ công; command không tự sửa.",
                )
            )

        expected_state = booking_state_service.derive_booking_status(rooms)
        if booking.status != expected_state:
            current_state = booking.status
            if apply:
                booking.status = expected_state
            issues.append(
                issue(
                    rule="booking_state",
                    entity_type="booking",
                    entity_id=booking.id,
                    current=current_state,
                    expected=expected_state,
                    can_apply=True,
                    applied=apply,
                )
            )

        expected_payment_status = _expected_payment_status(booking)
        if booking.payment_status != expected_payment_status:
            issues.append(
                issue(
                    rule="payment_status",
                    entity_type="booking",
                    entity_id=booking.id,
                    current=booking.payment_status,
                    expected=expected_payment_status,
                    note="Không tự suy đoán hoặc sửa trạng thái tài chính.",
                )
            )

        for booking_room in rooms:
            has_snapshot = bool(
                booking_room.price_breakdown_snapshot
                if booking_room.rental_type == "daily"
                else booking_room.hourly_price_snapshot
            )
            if not has_snapshot:
                issues.append(
                    issue(
                        rule="price_snapshot",
                        entity_type="booking_room",
                        entity_id=booking_room.id,
                        current="missing",
                        expected=f"{booking_room.rental_type}_snapshot",
                        note="Thiếu bằng chứng giá lịch sử; cần xử lý thủ công.",
                    )
                )
    return issues


def reconcile_payment_operations(hotel_id, *, apply):
    del apply
    issues = []
    payments = (
        Payment.query.filter_by(hotel_id=hotel_id)
        .order_by(Payment.id)
        .all()
    )
    for payment in payments:
        if (
            payment.payment_type in OPERATION_PAYMENT_TYPES
            and payment.business_operation_id is None
        ):
            issues.append(
                issue(
                    rule="payment_operation",
                    entity_type="payment",
                    entity_id=payment.id,
                    current="missing",
                    expected="business_operation",
                    note="Không tự tạo operation lịch sử khi thiếu bằng chứng.",
                )
            )
        elif (
            payment.business_operation is not None
            and payment.business_operation.hotel_id != hotel_id
        ):
            issues.append(
                issue(
                    rule="tenant_link",
                    entity_type="payment",
                    entity_id=payment.id,
                    current="mismatch",
                    expected="same_tenant",
                )
            )
    return issues


def reconcile_room_occupancy(hotel_id, *, apply):
    issues = []
    rooms = Room.query.filter_by(hotel_id=hotel_id).order_by(Room.id).all()
    for room in rooms:
        active_count = sum(
            1
            for booking_room in room.booking_history
            if (
                booking_room.hotel_id == hotel_id
                and booking_room.status == "checked_in"
            )
        )
        if active_count > 1:
            issues.append(
                issue(
                    rule="room_occupancy",
                    entity_type="room",
                    entity_id=room.id,
                    current=f"{active_count}_checked_in",
                    expected="exactly_one_checked_in",
                    note="Có nhiều lượt ở đồng thời; cần xử lý thủ công.",
                )
            )
            continue

        expected_status = "occupied" if active_count == 1 else "available"
        can_apply = room.status != "maintenance"
        if room.status != expected_status:
            current_status = room.status
            if apply and can_apply:
                room.status = expected_status
            issues.append(
                issue(
                    rule="room_occupancy",
                    entity_type="room",
                    entity_id=room.id,
                    current=current_status,
                    expected=expected_status,
                    can_apply=can_apply,
                    applied=apply and can_apply,
                    note=(
                        None
                        if can_apply
                        else "Phòng bảo trì có lượt ở; cần xử lý thủ công."
                    ),
                )
            )
    return issues
