from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from extensions import db
from models.booking import Booking
from models.business_operation import BusinessOperation
from models.payment import Payment


def _to_decimal_amount(amount) -> Decimal:
    if amount is None:
        return Decimal("0")
    # Payment.amount is Numeric; keep cents if provided.
    return Decimal(str(amount))


def _now(dt: Optional[datetime]) -> datetime:
    return dt if dt is not None else datetime.now()


def _create_payment(
    *,
    booking_id: int,
    amount,
    payment_type: str,
    note: str,
    payment_method: str = "cash",
    created_at: Optional[datetime] = None,
    flush: bool = False,
    business_operation: Optional[BusinessOperation] = None,
    component_key: Optional[str] = None,
    reverses_payment_id: Optional[int] = None,
) -> Payment:
    booking = db.session.get(Booking, booking_id)
    if booking is None:
        raise ValueError("Không tìm thấy booking để ghi nhận thanh toán.")

    if (business_operation is None) != (component_key is None):
        raise ValueError(
            "business_operation và component_key phải được cung cấp cùng nhau."
        )
    if (
        business_operation is not None
        and business_operation.hotel_id != booking.hotel_id
    ):
        raise ValueError(
            "BusinessOperation khác khách sạn với booking."
        )

    payment = Payment(
        hotel_id=booking.hotel_id,
        booking_id=booking_id,
        business_operation=business_operation,
        component_key=component_key,
        reverses_payment_id=reverses_payment_id,
        amount=_to_decimal_amount(amount),
        payment_method=payment_method,
        payment_type=payment_type,
        note=note,
        created_at=_now(created_at),
    )
    db.session.add(payment)
    if flush:
        db.session.flush()
    return payment


def record_deposit(
    *,
    booking_id: int,
    amount,
    note: str,
    payment_method: str = "cash",
    created_at: Optional[datetime] = None,
    flush: bool = False,
    business_operation: Optional[BusinessOperation] = None,
    component_key: Optional[str] = None,
) -> Payment:
    return _create_payment(
        booking_id=booking_id,
        amount=amount,
        payment_method=payment_method,
        payment_type="deposit",
        note=note,
        created_at=created_at,
        flush=flush,
        business_operation=business_operation,
        component_key=component_key,
    )


def record_room_payment(
    *,
    booking_id: int,
    amount,
    note: str,
    payment_method: str = "cash",
    created_at: Optional[datetime] = None,
    flush: bool = False,
    payment_type: str = "room_payment",
    business_operation: Optional[BusinessOperation] = None,
    component_key: Optional[str] = None,
) -> Payment:
    """Record a payment line for room/service settlement.

    Default payment_type is "room_payment"; controllers may pass "service_payment".
    """
    return _create_payment(
        booking_id=booking_id,
        amount=amount,
        payment_method=payment_method,
        payment_type=payment_type,
        note=note,
        created_at=created_at,
        flush=flush,
        business_operation=business_operation,
        component_key=component_key,
    )


def record_refund(
    *,
    booking_id: int,
    refund_amount,
    note: str,
    payment_method: str = "cash",
    created_at: Optional[datetime] = None,
    flush: bool = False,
    business_operation: Optional[BusinessOperation] = None,
    component_key: Optional[str] = None,
) -> Payment:
    """Record a refund as a negative amount in Payment (cashflow semantics)."""
    amt = abs(_to_decimal_amount(refund_amount))
    return _create_payment(
        booking_id=booking_id,
        amount=-amt,
        payment_method=payment_method,
        payment_type="refund",
        note=note,
        created_at=created_at,
        flush=flush,
        business_operation=business_operation,
        component_key=component_key,
    )


def record_cancellation_fee(
    *,
    booking_id: int,
    amount,
    note: str,
    payment_method: str = "cash",
    created_at: Optional[datetime] = None,
    flush: bool = False,
    business_operation: Optional[BusinessOperation] = None,
    component_key: Optional[str] = None,
) -> Payment:
    """Record a cancellation fee note.

    Legacy behavior stores 0 amount because the money is retained from an existing deposit.
    """
    return _create_payment(
        booking_id=booking_id,
        amount=_to_decimal_amount(amount),
        payment_method=payment_method,
        payment_type="cancellation_fee",
        note=note,
        created_at=created_at,
        flush=flush,
        business_operation=business_operation,
        component_key=component_key,
    )


def record_group_settlement(
    *,
    booking_id: int,
    amount,
    note: str,
    payment_method: str = "cash",
    created_at: Optional[datetime] = None,
    flush: bool = False,
    business_operation: Optional[BusinessOperation] = None,
    component_key: Optional[str] = None,
) -> Payment:
    return _create_payment(
        booking_id=booking_id,
        amount=amount,
        payment_method=payment_method,
        payment_type="settlement",
        note=note,
        created_at=created_at,
        flush=flush,
        business_operation=business_operation,
        component_key=component_key,
    )


def record_refund_reversal(
    *,
    booking_id: int,
    amount,
    note: str,
    reverses_payment_id: int,
    payment_method: str = "cash",
    created_at: Optional[datetime] = None,
    flush: bool = False,
    business_operation: Optional[BusinessOperation] = None,
    component_key: Optional[str] = None,
) -> Payment:
    """Bút toán đảo một dòng refund: dòng dương cùng số tiền, nối về dòng sai."""
    amt = abs(_to_decimal_amount(amount))
    return _create_payment(
        booking_id=booking_id,
        amount=amt,
        payment_method=payment_method,
        payment_type="refund_reversal",
        note=note,
        created_at=created_at,
        flush=flush,
        business_operation=business_operation,
        component_key=component_key,
        reverses_payment_id=reverses_payment_id,
    )


def effective_payments(booking) -> list:
    """Các dòng còn hiệu lực cho hóa đơn khách.

    Loại bỏ cặp đã triệt tiêu: dòng refund bị đảo và mọi dòng refund_reversal.
    Sổ quỹ/audit nội bộ KHÔNG dùng hàm này — nội bộ luôn xem đủ mọi dòng.
    """
    reversed_ids = {
        p.reverses_payment_id for p in booking.payments if p.reverses_payment_id
    }
    return [
        p
        for p in booking.payments
        if p.payment_type != "refund_reversal"
        and not (p.payment_type == "refund" and p.id in reversed_ids)
    ]
