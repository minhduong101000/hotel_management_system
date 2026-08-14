from decimal import Decimal, ROUND_HALF_UP

from services import (
    audit_service,
    booking_state_service,
    business_operation_service,
    payment_service,
)


MONEY_QUANTUM = Decimal("0.01")
ALLOWED_PAYMENT_METHODS = {
    "cash",
    "banking",
    "credit_card",
    "qr_code",
    "other",
}


def _money(value):
    return Decimal(str(value or 0)).quantize(
        MONEY_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def _payment_method(value):
    method = str(value or "cash").strip().lower()
    return method if method in ALLOWED_PAYMENT_METHODS else "cash"


def _allocate(balance, components):
    eligible = [
        (component_key, payment_type, _money(amount), note)
        for component_key, payment_type, amount, note in components
        if _money(amount) > 0
    ]
    if balance <= 0 or not eligible:
        return []

    denominator = sum((item[2] for item in eligible), Decimal("0"))
    remaining = _money(balance)
    allocations = []
    for index, (key, payment_type, amount, note) in enumerate(eligible):
        if index == len(eligible) - 1:
            allocated = remaining
        else:
            allocated = _money(balance * amount / denominator)
            remaining -= allocated
        allocations.append((key, payment_type, allocated, note))
    return allocations


def settle_group_checkout(
    *,
    booking,
    booking_rooms,
    quote,
    operation,
    payment_method,
    checkout_at,
    actor_user_id,
):
    """Chốt toàn bộ phòng đang ở trong một transaction do controller quản lý."""
    if not booking_rooms:
        raise booking_state_service.InvalidBookingTransition(
            "Không còn phòng đang ở để checkout đoàn."
        )
    if any(room.status != "checked_in" for room in booking_rooms):
        raise booking_state_service.InvalidBookingTransition(
            "Chỉ phòng đang ở mới được phép checkout đoàn."
        )

    quote_by_room = {
        int(room_quote["booking_room_id"]): room_quote
        for room_quote in quote["rooms"]
        if room_quote["include_in_settlement"]
    }
    components = []
    for booking_room in booking_rooms:
        room_quote = quote_by_room[booking_room.id]
        room_number = booking_room.room.room_number
        components.extend([
            (
                f"room:{booking_room.id}:room",
                "room_payment",
                room_quote["room_subtotal"],
                f"Thanh toán tiền phòng {room_number} (đoàn {booking.code})",
            ),
            (
                f"room:{booking_room.id}:service",
                "service_payment",
                room_quote["service_subtotal"],
                f"Thanh toán dịch vụ phòng {room_number} (đoàn {booking.code})",
            ),
            (
                f"room:{booking_room.id}:tax",
                "tax_payment",
                room_quote["tax"],
                f"Thuế VAT phòng {room_number} (đoàn {booking.code})",
            ),
        ])

    balance = _money(quote["balance"])
    method = _payment_method(payment_method)
    if balance > 0:
        for component_key, payment_type, amount, note in _allocate(
            balance,
            components,
        ):
            payment_service.record_room_payment(
                booking_id=booking.id,
                amount=amount,
                payment_method=method,
                payment_type=payment_type,
                note=note,
                created_at=checkout_at,
                business_operation=operation,
                component_key=component_key,
            )
    # Cọc thừa (balance < 0) KHÔNG tự hoàn — chính sách 14-08-2026: hoàn tiền
    # luôn là thao tác chủ động qua form hoàn tiền, có lưới an toàn riêng.
    unrefunded_credit = _money(abs(balance)) if balance < 0 else _money(0)

    before_data = {
        "status": booking.status,
        "payment_status": booking.payment_status,
        "room_ids": [room.room_id for room in booking_rooms],
        "prepaid_amount": format(_money(booking.prepaid_amount), ".2f"),
    }
    booking.prepaid_amount = Decimal("0")
    for room in booking.rooms:
        room.room_deposit_amount = Decimal("0")

    for booking_room in booking_rooms:
        room_quote = quote_by_room[booking_room.id]
        booking_state_service.finalize_room_checkout(
            booking_room,
            checkout_at=checkout_at,
            final_amount=room_quote["total"],
        )

    result = {
        "success": True,
        "msg": "Thanh toán đoàn thành công!",
        "operation_key": operation.operation_key,
        "data": {
            "total_bill": quote["settlement_total"],
            "booking_total": quote["booking_total"],
            "tax_amount": quote["tax"],
            "group_deposit": quote["deposit"],
            "final_amount_to_pay": quote["balance"],
            "unrefunded_credit": format(unrefunded_credit, ".2f"),
        },
    }
    business_operation_service.complete_operation(operation, result)
    audit_service.record_event(
        hotel_id=booking.hotel_id,
        actor_user_id=actor_user_id,
        action="group_checkout",
        entity_type="booking",
        entity_id=booking.id,
        operation_key=operation.operation_key,
        before_data=before_data,
        after_data={
            "status": booking.status,
            "payment_status": booking.payment_status,
            "room_count": len(booking_rooms),
            "total_bill": quote["settlement_total"],
            "booking_total": quote["booking_total"],
            "tax_amount": quote["tax"],
            "deposit_applied": quote["deposit"],
            "final_amount_to_pay": quote["balance"],
            "unrefunded_credit": format(unrefunded_credit, ".2f"),
        },
    )
    return result
