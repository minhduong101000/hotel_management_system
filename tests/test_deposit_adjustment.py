"""Giảm cọc phải để lại bút toán — chính sách chốt 19-08.

Sổ tiền là append-only: sửa số thì thêm dòng, không đè dòng cũ.
"""

from decimal import Decimal

import pytest

from extensions import db
from models import Payment
from services import payment_service


def test_record_deposit_adjustment_writes_a_negative_ledger_row(app, seed_hotels):
    _, _, _, _, br, _ = seed_hotels

    payment = payment_service.record_deposit_adjustment(
        booking_id=br.booking_id,
        amount=Decimal("-4500000"),
        note="Điều chỉnh cọc: gõ nhầm số 0",
    )
    db.session.commit()

    assert payment.payment_type == "deposit_adjustment"
    assert payment.amount == Decimal("-4500000.00")
    assert "gõ nhầm" in payment.note


def test_record_deposit_adjustment_rejects_a_positive_amount(app, seed_hotels):
    """Tăng cọc là nhận thêm tiền — phải đi qua record_deposit."""
    _, _, _, _, br, _ = seed_hotels

    with pytest.raises(ValueError):
        payment_service.record_deposit_adjustment(
            booking_id=br.booking_id,
            amount=Decimal("100000"),
            note="sai hướng",
        )


def test_adjustment_lowers_the_refund_cap(app, seed_hotels):
    """Trần hoàn tiền = tổng đã thu, nên phải tụt theo dòng âm."""
    from services import refund_service

    _, _, _, _, br, _ = seed_hotels
    payment_service.record_deposit(
        booking_id=br.booking_id, amount=Decimal("5000000"), note="Nhận cọc"
    )
    db.session.commit()
    cap_before = refund_service.refundable_cap(br.booking)

    payment_service.record_deposit_adjustment(
        booking_id=br.booking_id,
        amount=Decimal("-4500000"),
        note="Điều chỉnh cọc: gõ nhầm số 0",
    )
    db.session.commit()

    assert cap_before == Decimal("5000000.00")
    assert refund_service.refundable_cap(br.booking) == Decimal("500000.00")


def test_customer_bill_sees_the_net_deposit_not_the_correction_pair(app, seed_hotels):
    """Nội bộ thấy đủ hai dòng, hóa đơn khách chỉ thấy số ròng.

    Bảng "hoàn tiền" trên hóa đơn khách chỉ lọc payment_type == 'refund'
    (billing_controller), nên dòng điều chỉnh không lọt ra ngoài; còn tổng tiền
    đã thu là phép cộng nên tự trừ đi phần điều chỉnh.
    """
    _, _, _, _, br, _ = seed_hotels
    payment_service.record_deposit(
        booking_id=br.booking_id, amount=Decimal("5000000"), note="Nhận cọc"
    )
    payment_service.record_deposit_adjustment(
        booking_id=br.booking_id,
        amount=Decimal("-4500000"),
        note="Điều chỉnh cọc: gõ nhầm số 0",
    )
    db.session.commit()

    payments = br.booking.payments
    assert len(payments) == 2                                        # sổ nội bộ: đủ 2 dòng
    assert sum(p.amount for p in payments) == Decimal("500000.00")   # khách: số ròng
    assert not [p for p in payments if p.payment_type == "refund"]   # không phải hoàn tiền


def test_cashier_report_labels_the_adjustment(client, seed_hotels, login_as):
    hotel, _, admin, _, br, _ = seed_hotels
    payment_service.record_deposit_adjustment(
        booking_id=br.booking_id,
        amount=Decimal("-4500000"),
        note="Điều chỉnh cọc: gõ nhầm số 0",
    )
    db.session.commit()
    login_as(client, admin)   # sổ quỹ là @admin_required

    response = client.get(f"/{hotel.slug}/cashier/api/reports/cashier?period=week")

    assert response.status_code == 200
    labels = [row["type_label"] for row in response.get_json()["data"]["records"]]
    assert "Điều chỉnh cọc" in labels
