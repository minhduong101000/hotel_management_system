from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from extensions import db
from models import Payment
from models.audit_event import AuditEvent
from models.business_operation import BusinessOperation
from services import payment_service, refund_service


START = datetime(2026, 8, 10, 14, 0)


def _five_night_room(booking_room, checked_in=True):
    """5 đêm × 400k từ 10-08; snapshot breakdown đầy đủ từng đêm."""
    booking_room.rental_type = "daily"
    booking_room.check_in_expected = START
    booking_room.check_out_expected = START + timedelta(days=5) - timedelta(hours=2)
    booking_room.price_snapshot = Decimal("400000")
    booking_room.price_breakdown_snapshot = [
        {
            "business_date": (START + timedelta(days=i)).strftime("%Y-%m-%d"),
            "amount": 400000.0,
        }
        for i in range(5)
    ]
    if checked_in:
        booking_room.status = "checked_in"
        booking_room.check_in_actual = START
    db.session.flush()


def _fund(booking, amount):
    payment_service.record_deposit(
        booking_id=booking.id, amount=amount, note="Cọc test", flush=True
    )


def test_refund_base_unused_math(app, seed_hotels):
    hotel, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        _five_night_room(booking_room)
        _fund(booking_room.booking, 2_000_000)
        # Rời đi ngày 12-08: đã ở đêm 10, 11 -> còn 3 đêm chưa dùng
        effective_at = START + timedelta(days=2)

        quote = refund_service.quote_refund(
            booking=booking_room.booking,
            base="unused",
            percent=50,
            effective_at=effective_at,
        )
        assert quote["base_value"] == Decimal("1200000.00")
        assert quote["refund_amount"] == Decimal("600000.00")
        assert quote["cap"] == Decimal("2000000.00")

        payment = refund_service.create_refund(
            booking=booking_room.booking,
            base="unused",
            percent=50,
            effective_at=effective_at,
            payment_method="cash",
            reason="Bão, khách rời sớm",
            actor_user_id=user.id,
            client_key="t1",
        )
        assert payment.payment_type == "refund"
        assert payment.amount == Decimal("-600000.00")
        assert payment.hotel_id == hotel.id


def test_refund_base_total_math(app, seed_hotels):
    _, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        _five_night_room(booking_room)
        _fund(booking_room.booking, 2_000_000)

        payment = refund_service.create_refund(
            booking=booking_room.booking,
            base="total",
            percent=50,
            payment_method="banking",
            reason="Thỏa thuận thiện chí",
            actor_user_id=user.id,
            client_key="t2",
        )
        assert payment.amount == Decimal("-1000000.00")


def test_refund_amount_direct_entry(app, seed_hotels):
    _, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        _five_night_room(booking_room)
        _fund(booking_room.booking, 500_000)

        payment = refund_service.create_refund(
            booking=booking_room.booking,
            base="total",
            amount=350_000,
            payment_method="cash",
            reason="Trả một phần theo thỏa thuận",
            actor_user_id=user.id,
            client_key="t3",
        )
        assert payment.amount == Decimal("-350000.00")


def test_refund_hard_cap_blocks_over_refund(app, seed_hotels):
    _, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        _five_night_room(booking_room)
        _fund(booking_room.booking, 500_000)
        refund_service.create_refund(
            booking=booking_room.booking,
            base="total",
            amount=300_000,
            payment_method="cash",
            reason="Hoàn lần 1",
            actor_user_id=user.id,
            client_key="t4a",
        )
        audit_before = AuditEvent.query.count()

        with pytest.raises(refund_service.RefundError):
            refund_service.create_refund(
                booking=booking_room.booking,
                base="total",
                amount=300_000,  # cap còn 200k
                payment_method="cash",
                reason="Hoàn lần 2 vượt trần",
                actor_user_id=user.id,
                client_key="t4b",
            )

        assert Payment.query.filter_by(payment_type="refund").count() == 1
        assert AuditEvent.query.count() == audit_before


def test_refund_requires_reason_and_valid_method(app, seed_hotels):
    _, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        _five_night_room(booking_room)
        _fund(booking_room.booking, 500_000)

        with pytest.raises(refund_service.RefundError):
            refund_service.create_refund(
                booking=booking_room.booking, base="total", amount=100_000,
                payment_method="cash", reason="   ",
                actor_user_id=user.id, client_key="t5a",
            )
        with pytest.raises(refund_service.RefundError):
            refund_service.create_refund(
                booking=booking_room.booking, base="total", amount=100_000,
                payment_method="momo", reason="Phương thức lạ",
                actor_user_id=user.id, client_key="t5b",
            )
        assert Payment.query.filter_by(payment_type="refund").count() == 0


def test_refund_idempotent_retry_returns_same_payment(app, seed_hotels):
    _, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        _five_night_room(booking_room)
        _fund(booking_room.booking, 500_000)

        first = refund_service.create_refund(
            booking=booking_room.booking, base="total", amount=200_000,
            payment_method="cash", reason="Hoàn cọc",
            actor_user_id=user.id, client_key="same-key",
        )
        second = refund_service.create_refund(
            booking=booking_room.booking, base="total", amount=200_000,
            payment_method="cash", reason="Hoàn cọc",
            actor_user_id=user.id, client_key="same-key",
        )
        assert first.id == second.id
        assert Payment.query.filter_by(payment_type="refund").count() == 1


def test_refund_records_operation_and_audit(app, seed_hotels):
    hotel, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        _five_night_room(booking_room)
        _fund(booking_room.booking, 2_000_000)

        payment = refund_service.create_refund(
            booking=booking_room.booking, base="total", percent=10,
            payment_method="cash", reason="Hoàn 10%",
            actor_user_id=user.id, client_key="t7",
        )
        operation = BusinessOperation.query.filter_by(
            operation_key=f"refund:{booking_room.booking_id}:t7"
        ).one()
        assert operation.status == "completed"
        assert payment.business_operation_id == operation.id
        assert payment.component_key == "refund"

        event = AuditEvent.query.filter_by(action="create_refund").one()
        assert event.hotel_id == hotel.id
        assert event.actor_user_id == user.id
        assert event.after_data["base"] == "total"
        assert float(event.after_data["percent"]) == 10.0
        assert float(event.after_data["refund_amount"]) == 200000.0


def test_refund_unused_value_hourly_room_is_zero(app, seed_hotels):
    _, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        booking_room.rental_type = "hourly"
        booking_room.status = "checked_in"
        booking_room.check_in_actual = START
        booking_room.price_snapshot = Decimal("100000")
        db.session.flush()
        _fund(booking_room.booking, 300_000)

        quote = refund_service.quote_refund(
            booking=booking_room.booking, base="unused", percent=100,
            effective_at=START + timedelta(hours=1),
        )
        # Thuê giờ: đã ở là tính trọn block -> phần chưa dùng = 0
        assert quote["base_value"] == Decimal("0.00")
        assert quote["refund_amount"] == Decimal("0.00")


def test_refund_unused_value_falls_back_to_price_snapshot(app, seed_hotels):
    _, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        _five_night_room(booking_room)
        booking_room.price_breakdown_snapshot = None  # dữ liệu cũ chưa có snapshot
        db.session.flush()
        _fund(booking_room.booking, 2_000_000)

        quote = refund_service.quote_refund(
            booking=booking_room.booking, base="unused", percent=100,
            effective_at=START + timedelta(days=2),
        )
        # Fallback: 3 đêm còn lại × price_snapshot 400k
        assert quote["base_value"] == Decimal("1200000.00")
