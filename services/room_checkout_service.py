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


def _allocate_payment(balance, components):
    """Chia số tiền thực thu theo tỷ trọng, giữ tổng chính xác đến từng xu."""
    eligible = [
        (component_key, payment_type, _money(amount))
        for component_key, payment_type, amount in components
        if _money(amount) > 0
    ]
    if not eligible or balance <= 0:
        return []

    denominator = sum((item[2] for item in eligible), Decimal("0"))
    remaining = _money(balance)
    allocations = []
    for index, (component_key, payment_type, amount) in enumerate(eligible):
        if index == len(eligible) - 1:
            allocated = remaining
        else:
            allocated = _money(balance * amount / denominator)
            remaining -= allocated
        allocations.append((component_key, payment_type, allocated))
    return allocations


def settle_room_checkout(
    *,
    booking_room,
    quote,
    operation,
    payment_method,
    checkout_at,
    actor_user_id,
):
    """Quyết toán checkout dựa hoàn toàn trên báo giá đã xác thực."""
    if booking_room.status != "checked_in":
        raise booking_state_service.InvalidBookingTransition(
            "Chỉ phòng đang ở mới được phép checkout."
        )

    room_amount = _money(quote["room_subtotal"])
    service_amount = _money(quote["service_subtotal"])
    tax_amount = _money(quote["tax"])
    total = _money(quote["total"])
    balance = _money(quote["balance"])
    method = _payment_method(payment_method)
    booking = booking_room.booking
    room_number = booking_room.room.room_number

    if balance > 0:
        allocations = _allocate_payment(
            balance,
            (
                ("room_payment", "room_payment", room_amount),
                ("service_payment", "service_payment", service_amount),
                ("tax_payment", "tax_payment", tax_amount),
            ),
        )
        labels = {
            "room_payment": f"Thanh toán tiền phòng {room_number}",
            "service_payment": f"Thanh toán tiền dịch vụ phòng {room_number}",
            "tax_payment": f"Thuế VAT phòng {room_number}",
        }
        for component_key, payment_type, amount in allocations:
            payment_service.record_room_payment(
                booking_id=booking.id,
                amount=amount,
                payment_method=method,
                payment_type=payment_type,
                note=labels[component_key],
                created_at=checkout_at,
                business_operation=operation,
                component_key=component_key,
                created_by=actor_user_id,
            )
    # Cọc thừa KHÔNG tự hoàn (chính sách 14-08) — trả unrefunded_credit,
    # hoàn tiền là thao tác chủ động qua form hoàn tiền có lưới an toàn.

    if quote.get("apply_deposit"):
        booking.prepaid_amount = Decimal("0")
        for room_line in booking.rooms:
            room_line.room_deposit_amount = Decimal("0")

    booking_state_service.finalize_room_checkout(
        booking_room,
        checkout_at=checkout_at,
        final_amount=total,
    )

    result = {
        "success": True,
        "msg": f"Trả phòng {room_number} thành công!",
        "operation_key": operation.operation_key,
        "settled_amount": format(max(balance, Decimal("0")), ".2f"),
        "refund_amount": "0.00",
        "unrefunded_credit": format(abs(min(balance, Decimal("0"))), ".2f"),
        "balance_remaining": "0.00",
    }
    business_operation_service.complete_operation(operation, result)
    audit_service.record_event(
        hotel_id=booking_room.hotel_id,
        actor_user_id=actor_user_id,
        action="checkout",
        entity_type="booking_room",
        entity_id=booking_room.id,
        operation_key=operation.operation_key,
        before_data={"status": "checked_in"},
        after_data={
            "status": "checked_out",
            "final_amount": format(total, ".2f"),
        },
    )
    return result
