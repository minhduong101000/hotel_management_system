from decimal import Decimal


class InvalidBookingTransition(ValueError):
    """Trạng thái hiện tại không cho phép thực hiện chuyển trạng thái."""


def finalize_room_checkout(booking_room, *, checkout_at, final_amount):
    """Hoàn tất trạng thái phòng và tổng hợp trạng thái của đơn."""
    if booking_room.status != "checked_in":
        raise InvalidBookingTransition(
            "Chỉ phòng đang ở mới được phép checkout."
        )

    booking_room.status = "checked_out"
    booking_room.check_out_actual = checkout_at
    booking_room.final_amount = Decimal(str(final_amount))
    booking_room.room.status = "available"
    booking_room.room.clean_status = "dirty"

    booking = booking_room.booking
    all_rooms = list(booking.rooms)
    booking.total_amount = sum(
        (Decimal(str(room.final_amount or 0)) for room in all_rooms),
        Decimal("0"),
    )
    booking.updated_at = checkout_at

    if all(room.status in ("checked_out", "cancelled") for room in all_rooms):
        booking.status = "completed"
        booking.payment_status = "paid"
    else:
        booking.status = "checked_in"
        booking.payment_status = "partial"

    return booking
