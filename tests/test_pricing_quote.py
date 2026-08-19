from datetime import datetime

from extensions import db
from models import BookingService, Service
from services import booking_quote_service


def test_checkout_quote_contains_authoritative_money_components(seed_hotels):
    hotel, _, _, _, booking_room, _ = seed_hotels
    booking_room.status = "checked_in"
    # check_in_actual là UTC-naive (hợp đồng thời gian); 07:00 UTC = 14:00 VN.
    booking_room.check_in_actual = datetime(2030, 1, 1, 7, 0)
    # check_out_expected là giờ nghiệp vụ VN naive, không quy đổi.
    booking_room.check_out_expected = datetime(2030, 1, 2, 12, 0)
    booking_room.price_breakdown_snapshot = [
        {"business_date": "2030-01-01", "amount": 500000.0}
    ]
    service = Service(hotel_id=hotel.id, name="Nước suối", price=20000)
    db.session.add(service)
    db.session.flush()
    db.session.add(
        BookingService(
            hotel_id=hotel.id,
            booking_id=booking_room.booking_id,
            room_id=booking_room.room_id,
            service_id=service.id,
            quantity=2,
            price_at_booking=15000,
        )
    )
    db.session.commit()

    # checkout_at là mốc hệ thống UTC-naive; 05:00 UTC = 12:00 VN (đúng giờ hẹn trả).
    quote = booking_quote_service.build_checkout_quote(
        booking_room,
        checkout_at=datetime(2030, 1, 2, 5, 0),
        include_tax=True,
    )

    assert quote["version"] == "booking-quote-v1"
    assert quote["currency"] == "VND"
    assert quote["room_subtotal"] == "500000.00"
    assert quote["service_subtotal"] == "30000.00"
    assert quote["tax"] == "42400.00"
    assert quote["total"] == "572400.00"
    assert quote["balance"] == "572400.00"
    assert quote["room_lines"]
    assert quote["service_lines"] == [
        {
            "service_id": service.id,
            "name": "Nước suối",
            "quantity": 2,
            "unit_price": "15000.00",
            "amount": "30000.00",
        }
    ]
    assert len(quote["fingerprint"]) == 64
    # checkout_at trong quote giữ nguyên UTC (không quy đổi) vì được dùng cho
    # fingerprint và ghi vào check_out_actual.
    assert quote["checkout_at"] == "2030-01-02T05:00:00"
    assert quote["expires_at"]


def test_existing_booking_quote_uses_snapshot_after_price_rule_changes(
    seed_hotels,
):
    _, _, _, _, booking_room, _ = seed_hotels
    booking_room.status = "checked_in"
    # check_in_actual là UTC-naive; 07:00 UTC = 14:00 VN.
    booking_room.check_in_actual = datetime(2031, 5, 1, 7, 0)
    # check_out_expected là giờ nghiệp vụ VN naive, không quy đổi.
    booking_room.check_out_expected = datetime(2031, 5, 2, 12, 0)
    booking_room.price_breakdown_snapshot = [
        {"business_date": "2031-05-01", "amount": 420000.0}
    ]
    booking_room.room.price_per_night = 990000
    db.session.commit()

    # checkout_at là mốc hệ thống UTC-naive; 05:00 UTC = 12:00 VN.
    quote = booking_quote_service.build_checkout_quote(
        booking_room,
        checkout_at=datetime(2031, 5, 2, 5, 0),
        include_tax=False,
    )

    assert quote["room_subtotal"] == "420000.00"
    assert quote["room_lines"][0]["amount"] == "420000.00"
