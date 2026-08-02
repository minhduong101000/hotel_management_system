import pytest
from sqlalchemy import event

from extensions import db
from models import BookingRoom, Room, User


def test_room_settings_api_returns_current_tenant_room_configuration(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, admin, _, booking_room, _ = seed_hotels
    login_as(client, admin)

    response = client.get(f"/{hotel.slug}/rooms/api/settings")

    assert response.status_code == 200
    assert response.get_json() == {
        "rooms": [
            {
                "id": booking_room.room.id,
                "room_number": "101",
                "room_type": "Standard",
                "price_per_night": 500000.0,
                "price_initial_block": 300000.0,
                "initial_hours": 2,
                "price_next_hour": 50000.0,
                "status": "available",
                "clean_status": "cleaned",
                "active_booking_count": 1,
            }
        ],
        "room_types": ["Standard"],
    }


def test_room_settings_api_scopes_rooms_and_active_booking_counts_to_tenant(
    client,
    seed_hotels,
    login_as,
):
    hotel_a, hotel_b, admin, _, booking_room_a, booking_room_b = seed_hotels
    second_room = Room(
        hotel_id=hotel_a.id,
        room_number="102",
        room_type="Deluxe",
        price_per_night=800000,
        price_initial_block=450000,
        initial_hours=3,
        price_next_hour=100000,
    )
    db.session.add(second_room)
    db.session.flush()
    db.session.add_all([
        BookingRoom(
            hotel_id=hotel_a.id,
            booking_id=booking_room_a.booking_id,
            room_id=booking_room_a.room_id,
            status="cancelled",
        ),
        BookingRoom(
            hotel_id=hotel_a.id,
            booking_id=booking_room_a.booking_id,
            room_id=second_room.id,
            status="checked_in",
        ),
        BookingRoom(
            hotel_id=hotel_a.id,
            booking_id=booking_room_a.booking_id,
            room_id=second_room.id,
            status="checked_out",
        ),
    ])
    db.session.commit()
    login_as(client, admin)

    response = client.get(f"/{hotel_a.slug}/rooms/api/settings")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["room_types"] == ["Deluxe", "Standard"]
    assert payload["rooms"] == [
        {
            "id": booking_room_a.room.id,
            "room_number": "101",
            "room_type": "Standard",
            "price_per_night": 500000.0,
            "price_initial_block": 300000.0,
            "initial_hours": 2,
            "price_next_hour": 50000.0,
            "status": "available",
            "clean_status": "cleaned",
            "active_booking_count": 1,
        },
        {
            "id": second_room.id,
            "room_number": "102",
            "room_type": "Deluxe",
            "price_per_night": 800000.0,
            "price_initial_block": 450000.0,
            "initial_hours": 3,
            "price_next_hour": 100000.0,
            "status": "available",
            "clean_status": "cleaned",
            "active_booking_count": 1,
        },
    ]
    assert booking_room_b.room.id not in {room["id"] for room in payload["rooms"]}
    assert booking_room_b.room.hotel_id == hotel_b.id


def test_room_settings_api_is_available_to_staff_and_master_in_tenant_context(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, _, master, _, _ = seed_hotels
    staff = User(username="room_settings_staff", role="staff", hotel_id=hotel.id)
    staff.set_password("correct-password")
    db.session.add(staff)
    db.session.commit()

    login_as(client, staff)
    staff_response = client.get(f"/{hotel.slug}/rooms/api/settings")

    client.get(f"/{hotel.slug}/logout")
    login_as(client, master)
    master_response = client.get(f"/{hotel.slug}/rooms/api/settings")

    assert staff_response.status_code == 200
    assert master_response.status_code == 200


@pytest.mark.parametrize("room_total", [4, 40])
def test_room_settings_api_query_count_does_not_grow_with_room_total(
    client,
    seed_hotels,
    login_as,
    room_total,
):
    hotel, _, admin, _, _, _ = seed_hotels
    for number in range(2, room_total + 1):
        db.session.add(
            Room(
                hotel_id=hotel.id,
                room_number=f"{number:03d}",
                room_type="Standard",
                price_per_night=500000,
                price_initial_block=300000,
                initial_hours=2,
            )
        )
    db.session.commit()
    login_as(client, admin)

    statements = []

    def count_statement(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", count_statement)
    try:
        response = client.get(f"/{hotel.slug}/rooms/api/settings")
    finally:
        event.remove(db.engine, "before_cursor_execute", count_statement)

    assert response.status_code == 200
    assert len(response.get_json()["rooms"]) == room_total
    assert len(statements) <= 2, "\n\n".join(statements)
