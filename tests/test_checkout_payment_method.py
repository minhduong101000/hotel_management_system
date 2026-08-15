"""Chọn phương thức thanh toán khi checkout (thiết kế 15-08).

Server đã nhận payment_method trong payload — test 1 khóa hợp đồng đó.
Test 2 khóa UI: segmented Tiền mặt/Chuyển khoản/Thẻ + JS đọc lựa chọn
thay vì hardcode 'cash'.
"""

from datetime import datetime
from pathlib import Path

from extensions import db
from models import Payment

ROOT = Path(__file__).resolve().parents[1]


def test_checkout_records_selected_payment_method(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.status = "checked_in"
    booking_room.check_in_actual = datetime.now()
    booking_room.room.status = "occupied"
    db.session.commit()
    login_as(client, user)

    preview = client.post(
        f"/{hotel.slug}/bookings/api/rooms/preview_checkout",
        json={"number": booking_room.room.room_number},
    )
    quote = preview.json["quote"]

    response = client.post(
        f"/{hotel.slug}/bookings/api/rooms/checkout",
        json={
            "number": booking_room.room.room_number,
            "booking_room_id": booking_room.id,
            "booking_id": booking_room.booking_id,
            "include_tax": False,
            "payment_method": "banking",
            "quote_fingerprint": quote["fingerprint"],
            "quote_checkout_at": quote["checkout_at"],
        },
    )

    assert response.status_code == 200
    settlements = Payment.query.filter(Payment.payment_type != "deposit").all()
    assert settlements, "checkout phải ghi ít nhất 1 dòng thanh toán"
    assert all(p.payment_method == "banking" for p in settlements)


def test_checkout_modal_offers_payment_method_segment_and_js_reads_it():
    modal = (ROOT / "templates/rooms/_checkout_modal.html").read_text(encoding="utf-8")
    script = (ROOT / "static/js/checkout.js").read_text(encoding="utf-8")

    assert 'id="co-payment-method"' in modal
    for method in ("cash", "banking", "credit_card"):
        assert f'data-method="{method}"' in modal
    assert "setCheckoutPaymentMethod" in modal

    assert "function setCheckoutPaymentMethod" in script
    assert "function getCheckoutPaymentMethod" in script
    assert "inputId = 'co-payment-method'" in script
    assert "payment_method: getCheckoutPaymentMethod(" in script
    assert "payment_method: 'cash'," not in script
