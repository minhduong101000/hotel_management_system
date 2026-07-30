from decimal import Decimal


class InvalidBookingTransition(ValueError):
    """Trạng thái hiện tại không cho phép thực hiện chuyển trạng thái."""


TERMINAL_ROOM_STATUSES = frozenset({"checked_out", "cancelled"})


def _money(value):
    return Decimal(str(value or 0))


def _derive_booking_status(booking_rooms):
    statuses = {room.status for room in booking_rooms}
    if not statuses:
        return "pending"
    if statuses == {"cancelled"}:
        return "cancelled"
    if statuses.issubset(TERMINAL_ROOM_STATUSES) and "checked_out" in statuses:
        return "completed"
    if "checked_in" in statuses:
        return "checked_in"
    if "booked" in statuses:
        return "confirmed"
    return "pending"


def aggregate_booking_state(booking, *, changed_at=None):
    """Tính lại trạng thái và tổng tiền booking từ toàn bộ phòng con."""
    booking_rooms = list(booking.rooms)
    booking.status = _derive_booking_status(booking_rooms)
    booking.total_amount = sum(
        (_money(room.final_amount) for room in booking_rooms),
        Decimal("0"),
    )
    if changed_at is not None:
        booking.updated_at = changed_at

    if booking.status == "completed":
        booking.payment_status = "paid"
    elif booking.status == "checked_in":
        booking.payment_status = "partial"

    return booking


def _sync_physical_room(room):
    if any(
        booking_room.status == "checked_in"
        for booking_room in room.booking_history
    ):
        room.status = "occupied"
    elif room.status != "maintenance":
        room.status = "available"
    return room


def check_in_room(booking_room, *, checked_in_at):
    if booking_room.status != "booked":
        raise InvalidBookingTransition(
            "Chỉ phòng đã đặt mới được phép check-in."
        )

    booking_room.status = "checked_in"
    booking_room.check_in_actual = checked_in_at
    _sync_physical_room(booking_room.room)
    return aggregate_booking_state(
        booking_room.booking,
        changed_at=checked_in_at,
    )


def ensure_cancellable_rooms(booking_rooms):
    rooms = list(booking_rooms)
    if not rooms or any(room.status != "booked" for room in rooms):
        raise InvalidBookingTransition(
            "Chỉ phòng đã đặt mới được phép hủy."
        )
    return rooms


def cancel_rooms(booking_rooms, *, cancelled_at):
    rooms = ensure_cancellable_rooms(booking_rooms)

    for booking_room in rooms:
        booking_room.status = "cancelled"
        booking_room.check_out_actual = cancelled_at

    for booking_room in rooms:
        _sync_physical_room(booking_room.room)

    bookings = {}
    for booking_room in rooms:
        bookings[booking_room.booking_id] = booking_room.booking
    for booking in bookings.values():
        aggregate_booking_state(booking, changed_at=cancelled_at)

    return list(bookings.values())


def ensure_reschedulable(booking_room):
    if booking_room.status != "booked":
        raise InvalidBookingTransition(
            "Chỉ phòng đã đặt mới được phép dời lịch."
        )
    return booking_room


def finalize_room_checkout(booking_room, *, checkout_at, final_amount):
    """Hoàn tất trạng thái phòng và tổng hợp trạng thái của đơn."""
    if booking_room.status != "checked_in":
        raise InvalidBookingTransition(
            "Chỉ phòng đang ở mới được phép checkout."
        )

    booking_room.status = "checked_out"
    booking_room.check_out_actual = checkout_at
    booking_room.final_amount = _money(final_amount)
    _sync_physical_room(booking_room.room)
    if booking_room.room.status == "available":
        booking_room.room.clean_status = "dirty"

    return aggregate_booking_state(
        booking_room.booking,
        changed_at=checkout_at,
    )
