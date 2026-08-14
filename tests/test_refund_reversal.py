from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from extensions import db
from models import Payment
from services import payment_service, refund_service


START = datetime(2026, 8, 10, 14, 0)


def _checked_out_room(booking_room):
    booking_room.rental_type = "daily"
    booking_room.status = "checked_out"
    booking_room.check_in_actual = START
    booking_room.check_out_actual = START + timedelta(days=1)
    booking_room.final_amount = Decimal("400000")
    db.session.flush()


def _fund(booking, amount):
    payment_service.record_deposit(
        booking_id=booking.id, amount=amount, note="Cọc test", flush=True
    )


def _refund(booking, amount, user, key):
    return refund_service.create_refund(
        booking=booking, base="total", amount=amount,
        payment_method="cash", reason="Hoàn thử nghiệm",
        actor_user_id=user.id, client_key=key,
    )


def _wrong_then_corrected(booking_room, user):
    """Kịch bản chuẩn: nộp 500k, hoàn sai 350k -> đảo -> hoàn đúng 35k."""
    _checked_out_room(booking_room)
    booking = booking_room.booking
    _fund(booking, 500_000)
    wrong = _refund(booking, 350_000, user, "wrong")
    refund_service.reverse_refund(
        payment=wrong, reason="Nhập nhầm 70% thay vì 7%",
        actor_user_id=user.id, client_key="fix",
    )
    correct = _refund(booking, 35_000, user, "correct")
    return booking, wrong, correct


def test_reverse_refund_creates_linked_positive_line(app, seed_hotels):
    hotel, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        _checked_out_room(booking_room)
        _fund(booking_room.booking, 500_000)
        wrong = _refund(booking_room.booking, 350_000, user, "w1")

        reversal = refund_service.reverse_refund(
            payment=wrong, reason="Nhập nhầm",
            actor_user_id=user.id, client_key="r1",
        )
        assert reversal.payment_type == "refund_reversal"
        assert reversal.amount == Decimal("350000.00")
        assert reversal.reverses_payment_id == wrong.id
        assert reversal.hotel_id == hotel.id
        # Trần hoàn hồi phục lại sau khi đảo
        assert refund_service.refundable_cap(booking_room.booking) == Decimal("500000.00")


def test_reverse_refund_twice_rejected(app, seed_hotels):
    _, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        _checked_out_room(booking_room)
        _fund(booking_room.booking, 500_000)
        wrong = _refund(booking_room.booking, 100_000, user, "w2")
        refund_service.reverse_refund(
            payment=wrong, reason="Sai", actor_user_id=user.id, client_key="r2a",
        )
        with pytest.raises(refund_service.RefundError):
            refund_service.reverse_refund(
                payment=wrong, reason="Sai lần nữa",
                actor_user_id=user.id, client_key="r2b",
            )
        assert Payment.query.filter_by(payment_type="refund_reversal").count() == 1


def test_reverse_only_refund_lines(app, seed_hotels):
    _, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        _checked_out_room(booking_room)
        _fund(booking_room.booking, 500_000)
        deposit = Payment.query.filter_by(payment_type="deposit").one()
        with pytest.raises(refund_service.RefundError):
            refund_service.reverse_refund(
                payment=deposit, reason="Không hợp lệ",
                actor_user_id=user.id, client_key="r3",
            )


def test_effective_payments_hides_cancelled_pair(app, seed_hotels):
    _, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        booking, wrong, correct = _wrong_then_corrected(booking_room, user)
        effective = payment_service.effective_payments(booking)
        types = sorted(p.payment_type for p in effective)
        assert types == ["deposit", "refund"]
        refund_lines = [p for p in effective if p.payment_type == "refund"]
        assert refund_lines[0].id == correct.id


def test_billing_detail_shows_only_effective_refunds(app, seed_hotels, client, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        booking, _, _ = _wrong_then_corrected(booking_room, user)
        db.session.commit()
        login_as(client, user)

        response = client.get(
            f"/{hotel.slug}/billing/api/billing/detail/{booking.id}?type=booking"
        )
        assert response.status_code == 200
        data = response.json["data"]
        assert [r["amount"] for r in data["refunds"]] == [35000.0]
        # Sổ ròng: 500k nộp - 350k sai + 350k đảo - 35k đúng = 465k
        assert data["final_payment"] == 465000.0


def test_cashier_ledger_keeps_all_lines_with_labels(app, seed_hotels, client, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        booking, wrong, correct = _wrong_then_corrected(booking_room, user)
        db.session.commit()
        login_as(client, user)

        response = client.get(f"/{hotel.slug}/cashier/api/reports/cashier?period=today")
        assert response.status_code == 200
        records = response.json["data"]["records"]
        by_id = {r["id"]: r for r in records}
        assert f"p_{wrong.id}" in by_id, "sổ quỹ phải giữ dòng hoàn sai"
        assert by_id[f"p_{wrong.id}"]["is_reversed"] is True
        assert by_id[f"p_{correct.id}"]["is_reversed"] is False
        reversal_rows = [r for r in records if r["type_raw"] == "refund_reversal"]
        assert len(reversal_rows) == 1
        assert reversal_rows[0]["type_label"] == "Điều chỉnh hoàn tiền"
        # Két ròng khớp: 500k + 350k(đảo) thu vào, 385k hoàn ra
        data = response.json["data"]
        assert data["total_received"] == 850000.0
        assert data["total_refunded"] == 385000.0
        assert data["net_amount"] == 465000.0
