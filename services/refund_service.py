"""Hoàn tiền nhập trực tiếp có lưới an toàn (chính sách 14-08-2026).

Mọi con số do server tính; client chỉ gửi cơ sở tính, % hoặc số tiền,
phương thức, lý do. Trần cứng: tiền hoàn không vượt tổng tiền ròng đang
giữ của booking (Σ Payment.amount, đã tính mọi lần hoàn/đảo trước đó).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from extensions import db
from models.business_operation import BusinessOperation
from models.payment import Payment
from services import audit_service, business_operation_service, payment_service


MONEY_QUANTUM = Decimal("0.01")
ALLOWED_BASES = {"unused", "total"}
ALLOWED_PAYMENT_METHODS = {"cash", "banking", "credit_card", "qr_code", "other"}


class RefundError(ValueError):
    """Yêu cầu hoàn tiền không hợp lệ; không có mutation nào được ghi."""


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def refundable_cap(booking) -> Decimal:
    """Tiền ròng đang giữ của booking = Σ mọi dòng Payment (kể cả refund/đảo)."""
    total = (
        db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0))
        .filter(
            Payment.booking_id == booking.id,
            Payment.hotel_id == booking.hotel_id,
        )
        .scalar()
    )
    return _money(total)


def already_refunded_net(booking) -> Decimal:
    """Số đã hoàn ròng = |Σ refund| − Σ refund_reversal (cặp đảo triệt tiêu)."""
    refunded = (
        db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0))
        .filter(
            Payment.booking_id == booking.id,
            Payment.hotel_id == booking.hotel_id,
            Payment.payment_type.in_(["refund", "refund_reversal"]),
        )
        .scalar()
    )
    return _money(-Decimal(str(refunded or 0)))


def _room_nights_value(booking_room) -> Decimal:
    """Tổng giá trị đêm của một phòng theo snapshot; fallback theo price_snapshot."""
    snapshot = booking_room.price_breakdown_snapshot
    if snapshot:
        return _money(sum(Decimal(str(line["amount"])) for line in snapshot))
    if booking_room.rental_type != "daily":
        return _money(booking_room.price_snapshot)
    check_in = booking_room.check_in_expected
    check_out = booking_room.check_out_expected
    if not check_in or not check_out:
        return _money(booking_room.price_snapshot)
    nights = max(1, (check_out.date() - check_in.date()).days)
    return _money(Decimal(str(booking_room.price_snapshot or 0)) * nights)


def unused_value(booking, effective_at: Optional[datetime] = None) -> Decimal:
    """Giá trị các đêm CHƯA dùng tính từ effective_at.

    Quy tắc: đêm có business_date >= ngày rời đi là chưa dùng. Thuê giờ đã ở
    tính trọn block nên phần chưa dùng luôn bằng 0. Phòng đã checkout/hủy: 0.
    """
    effective_at = effective_at or datetime.now()
    effective_str = effective_at.strftime("%Y-%m-%d")
    total = Decimal("0")
    for booking_room in booking.rooms:
        if booking_room.status not in ("booked", "checked_in"):
            continue
        if booking_room.rental_type != "daily":
            continue
        snapshot = booking_room.price_breakdown_snapshot
        if snapshot:
            total += sum(
                Decimal(str(line["amount"]))
                for line in snapshot
                if line["business_date"] >= effective_str
            )
            continue
        check_in = booking_room.check_in_expected
        check_out = booking_room.check_out_expected
        if not check_in or not check_out:
            continue
        remaining_from = max(effective_at.date(), check_in.date())
        remaining_nights = max(0, (check_out.date() - remaining_from).days)
        total += Decimal(str(booking_room.price_snapshot or 0)) * remaining_nights
    return _money(total)


def total_value(booking) -> Decimal:
    """Toàn bộ hóa đơn: giá trị phòng chưa hủy + dịch vụ đã gọi."""
    total = Decimal("0")
    for booking_room in booking.rooms:
        if booking_room.status == "cancelled":
            continue
        total += _room_nights_value(booking_room)
    for line in booking.services:
        total += Decimal(str(line.price_at_booking or 0)) * (line.quantity or 0)
    return _money(total)


def quote_refund(
    *,
    booking,
    base: str,
    percent=None,
    amount=None,
    effective_at: Optional[datetime] = None,
) -> dict:
    """Tính báo giá hoàn tiền — dùng cho preview lẫn validate. Không mutation."""
    if base not in ALLOWED_BASES:
        raise RefundError("Cơ sở tính hoàn tiền không hợp lệ (unused/total).")
    if (percent is None) == (amount is None):
        raise RefundError("Nhập đúng một trong hai: phần trăm hoặc số tiền.")
    if percent is not None:
        try:
            percent = Decimal(str(percent))
        except ArithmeticError as exc:  # pragma: no cover - defensive
            raise RefundError("Phần trăm hoàn không hợp lệ.") from exc
        if percent <= 0 or percent > 100:
            raise RefundError("Phần trăm hoàn phải trong khoảng (0, 100].")

    base_value = (
        unused_value(booking, effective_at) if base == "unused" else total_value(booking)
    )
    if amount is not None:
        refund_amount = _money(amount)
    else:
        refund_amount = _money(base_value * percent / Decimal("100"))

    return {
        "base": base,
        "percent": float(percent) if percent is not None else None,
        "base_value": base_value,
        "refund_amount": refund_amount,
        "cap": refundable_cap(booking),
        "already_refunded": already_refunded_net(booking),
    }


def create_refund(
    *,
    booking,
    base: str,
    percent=None,
    amount=None,
    payment_method: str,
    reason: str,
    effective_at: Optional[datetime] = None,
    actor_user_id: int,
    client_key: str,
) -> Payment:
    """Ghi một dòng hoàn tiền (Payment âm) với đầy đủ lưới an toàn + audit.

    Idempotent theo (booking, client_key): gọi lại trả về đúng Payment cũ.
    Transaction do caller quản lý (service chỉ flush).
    """
    reason = (reason or "").strip()
    if not reason:
        raise RefundError("Cần nhập lý do hoàn tiền.")
    method = str(payment_method or "").strip().lower()
    if method not in ALLOWED_PAYMENT_METHODS:
        raise RefundError("Phương thức hoàn tiền không hợp lệ.")
    client_key = str(client_key or "").strip()
    if not client_key:
        raise RefundError("Thiếu client_key cho idempotency.")

    operation_key = f"refund:{booking.id}:{client_key}"
    existing = (
        BusinessOperation.query.filter_by(
            hotel_id=booking.hotel_id,
            operation_key=operation_key,
        ).first()
    )
    if existing is not None:
        return Payment.query.filter_by(
            business_operation_id=existing.id,
            component_key="refund",
        ).one()

    quote = quote_refund(
        booking=booking,
        base=base,
        percent=percent,
        amount=amount,
        effective_at=effective_at,
    )
    refund_amount = quote["refund_amount"]
    if refund_amount <= 0:
        raise RefundError("Số tiền hoàn phải lớn hơn 0.")
    if refund_amount > quote["cap"]:
        raise RefundError(
            "Số tiền hoàn vượt quá tiền đang giữ của đơn "
            f"(tối đa {quote['cap']:,.0f} đ)."
        )

    operation = BusinessOperation(
        hotel_id=booking.hotel_id,
        operation_key=operation_key,
        action="create_refund",
        entity_type="booking",
        entity_id=booking.id,
        request_fingerprint=business_operation_service.request_fingerprint(
            {
                "base": base,
                "percent": quote["percent"],
                "amount": format(refund_amount, ".2f"),
                "payment_method": method,
                "reason": reason,
            }
        ),
    )
    db.session.add(operation)
    db.session.flush()

    payment = payment_service.record_refund(
        booking_id=booking.id,
        refund_amount=refund_amount,
        payment_method=method,
        note=f"Hoàn tiền đơn {booking.code}: {reason}",
        business_operation=operation,
        component_key="refund",
        flush=True,
    )

    result = {
        "success": True,
        "payment_id": payment.id,
        "refund_amount": format(refund_amount, ".2f"),
        "base": base,
        "percent": quote["percent"],
    }
    business_operation_service.complete_operation(operation, result)
    audit_service.record_event(
        hotel_id=booking.hotel_id,
        actor_user_id=actor_user_id,
        action="create_refund",
        entity_type="booking",
        entity_id=booking.id,
        operation_key=operation_key,
        before_data={
            "cap": format(quote["cap"], ".2f"),
            "already_refunded": format(quote["already_refunded"], ".2f"),
        },
        after_data={
            "base": base,
            "percent": quote["percent"],
            "base_value": format(quote["base_value"], ".2f"),
            "refund_amount": format(refund_amount, ".2f"),
            "payment_method": method,
            "reason": reason,
        },
    )
    return payment
