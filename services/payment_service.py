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


DEPOSIT_PAYMENT_METHODS = ("cash", "banking", "credit_card")

# Nhãn tiếng Việt hiển thị cho từng phương thức — dùng ở Sổ Quỹ và các nơi
# khác cần diễn giải payment_method cho người đọc thay vì mã nội bộ.
PAYMENT_METHOD_LABELS = {
    "cash": "Tiền mặt",
    "banking": "Chuyển khoản",
    "credit_card": "Thẻ",
}


def normalize_payment_method(value, *, default: str = "cash") -> str:
    """Chuẩn hoá phương thức thanh toán do client gửi lên.

    Giá trị lạ bị quy về mặc định thay vì ném lỗi: đây là nhãn kế toán, không
    phải điều kiện an toàn — chặn cứng sẽ làm hỏng thao tác của lễ tân vì một
    lỗi gõ, trong khi hậu quả tệ nhất của việc quy về mặc định chỉ là một nhãn
    cần sửa sau.
    """
    candidate = str(value or "").strip().lower()
    return candidate if candidate in DEPOSIT_PAYMENT_METHODS else default


def _now(dt: Optional[datetime]) -> datetime:
    # Hợp đồng thời gian 14-08-2026: dòng tiền ghi UTC-naive qua time_service
    from services import time_service

    return dt if dt is not None else time_service.utc_now_naive()


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
    created_by: Optional[int] = None,
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
        created_by=created_by,
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
    created_by: Optional[int] = None,
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
        created_by=created_by,
    )


def record_deposit_adjustment(
    *,
    booking_id: int,
    amount,
    note: str,
    payment_method: str = "cash",
    created_at: Optional[datetime] = None,
    flush: bool = False,
    business_operation: Optional[BusinessOperation] = None,
    component_key: Optional[str] = None,
    created_by: Optional[int] = None,
) -> Payment:
    """Ghi một dòng ÂM khi tiền cọc bị điều chỉnh giảm.

    Sổ tiền là append-only: sửa số cọc thì thêm dòng đối ứng, không sửa dòng cũ.
    Đây KHÔNG phải hoàn tiền cho khách (dùng refund_service) mà là điều chỉnh
    số đã ghi nhận — ví dụ lễ tân gõ dư một số 0.
    """
    normalized = _to_decimal_amount(amount)
    if normalized >= 0:
        raise ValueError("record_deposit_adjustment chỉ nhận số âm; tăng cọc dùng record_deposit.")

    return _create_payment(
        booking_id=booking_id,
        amount=normalized,
        payment_method=payment_method,
        payment_type="deposit_adjustment",
        note=note,
        created_at=created_at,
        flush=flush,
        business_operation=business_operation,
        component_key=component_key,
        created_by=created_by,
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
    created_by: Optional[int] = None,
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
        created_by=created_by,
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
    created_by: Optional[int] = None,
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
        created_by=created_by,
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
    created_by: Optional[int] = None,
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
        created_by=created_by,
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
    created_by: Optional[int] = None,
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
        created_by=created_by,
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
    created_by: Optional[int] = None,
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
        created_by=created_by,
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
