from datetime import datetime
from decimal import Decimal

from extensions import db, mail
from services import notification_service


def test_booking_notification_builds_from_room_level_fields(
    app, seed_hotels, monkeypatch
):
    hotel, _, _, _, booking_room, _ = seed_hotels
    with app.app_context():
        hotel.email = "owner@test.vn"
        booking_room.rental_type = "daily"
        booking_room.check_in_expected = datetime(2026, 9, 1, 14, 0)
        booking_room.check_out_expected = datetime(2026, 9, 4, 12, 0)
        booking = booking_room.booking
        booking.prepaid_amount = Decimal("500000")
        db.session.commit()

        # Thread chạy đồng bộ để bắt được message trong test
        class SyncThread:
            def __init__(self, target=None, args=()):
                self.target, self.args = target, args

            def start(self):
                self.target(*self.args)

        monkeypatch.setattr(notification_service.threading, "Thread", SyncThread)

        with mail.record_messages() as outbox:
            notification_service.send_booking_notification(booking, hotel)

        assert len(outbox) == 1
        body = outbox[0].body
        assert booking.code in body
        assert "101" in body                # số phòng từ BookingRoom
        assert "14:00 01/09/2026" in body   # giờ vào của phòng
        assert "Theo ngày" in body
        assert "500,000" in body            # cọc từ booking.prepaid_amount


def test_booking_notification_skips_hotel_without_email(app, seed_hotels):
    hotel, _, _, _, booking_room, _ = seed_hotels
    with app.app_context():
        hotel.email = None
        db.session.commit()
        with mail.record_messages() as outbox:
            notification_service.send_booking_notification(
                booking_room.booking, hotel
            )
        assert outbox == []
