from extensions import db
from models import BookingService, Service


def test_checked_in_room_order_history_is_scoped_to_current_tenant(client, seed_hotels, login_as):
    hotel_a, hotel_b, user_a, _, booking_room_a, booking_room_b = seed_hotels
    booking_room_a.status = "checked_in"
    booking_room_b.status = "checked_in"
    service_a = Service(hotel_id=hotel_a.id, name="Nước suối", price=15000)
    service_b = Service(hotel_id=hotel_b.id, name="Không được lộ", price=99000)
    db.session.add_all([service_a, service_b])
    db.session.flush()
    db.session.add_all([
        BookingService(hotel_id=hotel_a.id, booking_id=booking_room_a.booking_id, room_id=booking_room_a.room_id, service_id=service_a.id, quantity=2, price_at_booking=15000),
        BookingService(hotel_id=hotel_b.id, booking_id=booking_room_b.booking_id, room_id=booking_room_b.room_id, service_id=service_b.id, quantity=1, price_at_booking=99000),
    ])
    db.session.commit()

    login_as(client, user_a)
    response = client.get(f"/{hotel_a.slug}/bookings/api/bookings/orders/room/{booking_room_a.room.room_number}")

    assert response.status_code == 200
    assert response.json == {
        "items": [{"service_name": "Nước suối", "quantity": 2, "price": 15000.0, "total": 30000.0}],
        "total": 30000.0,
    }


def test_order_history_rejects_room_without_checked_in_booking(client, seed_hotels, login_as):
    hotel_a, _, user_a, _, booking_room_a, _ = seed_hotels
    login_as(client, user_a)

    response = client.get(f"/{hotel_a.slug}/bookings/api/bookings/orders/room/{booking_room_a.room.room_number}")

    assert response.status_code == 404
