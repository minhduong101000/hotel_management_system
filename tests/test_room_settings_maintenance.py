import pytest

from extensions import db
from models import AuditEvent, Room, User


def _maintenance_url(hotel, room):
    return f"/{hotel.slug}/rooms/api/settings/{room.id}/maintenance"


def test_staff_cannot_change_room_maintenance(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, _, _, booking_room, _ = seed_hotels
    staff = User(
        username="maintenance_staff",
        role="staff",
        hotel_id=hotel.id,
    )
    staff.set_password("correct-password")
    db.session.add(staff)
    db.session.commit()
    login_as(client, staff)

    response = client.patch(
        _maintenance_url(hotel, booking_room.room),
        json={"maintenance": True},
    )

    assert response.status_code == 403
    assert response.get_json()["error_code"] == "forbidden"
    assert booking_room.room.status == "available"


def test_hotel_admin_enables_maintenance_without_active_bookings(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, admin, _, _, _ = seed_hotels
    room = Room(
        hotel_id=hotel.id,
        room_number="102",
        room_type="Standard",
        price_per_night=500000,
        price_initial_block=300000,
        initial_hours=2,
        price_next_hour=50000,
    )
    db.session.add(room)
    db.session.commit()
    login_as(client, admin)

    response = client.patch(
        _maintenance_url(hotel, room),
        json={"maintenance": True},
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert response.get_json()["room"]["status"] == "maintenance"
    assert response.get_json()["active_booking_count"] == 0
    assert response.get_json()["warning"] is False
    assert db.session.get(Room, room.id).clean_status == "cleaned"


def test_master_admin_clears_maintenance_for_selected_tenant(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, _, master_admin, booking_room, _ = seed_hotels
    booking_room.room.status = "maintenance"
    db.session.commit()
    login_as(client, master_admin)

    response = client.patch(
        _maintenance_url(hotel, booking_room.room),
        json={"maintenance": False},
    )

    assert response.status_code == 200
    assert db.session.get(Room, booking_room.room_id).status == "available"


def test_maintenance_change_does_not_disclose_other_tenant_room(
    client,
    seed_hotels,
    login_as,
):
    hotel_a, _, admin_a, _, _, booking_room_b = seed_hotels
    login_as(client, admin_a)

    response = client.patch(
        _maintenance_url(hotel_a, booking_room_b.room),
        json={"maintenance": True},
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"maintenance": "true"},
        {"maintenance": 1},
        [],
    ],
)
def test_maintenance_change_requires_boolean_flag(
    client,
    seed_hotels,
    login_as,
    payload,
):
    hotel, _, admin, _, booking_room, _ = seed_hotels
    login_as(client, admin)

    response = client.patch(
        _maintenance_url(hotel, booking_room.room),
        json=payload,
    )

    assert response.status_code == 400
    assert response.get_json()["error_code"] == "validation_error"
    assert booking_room.room.status == "available"


def test_enable_maintenance_keeps_existing_booking_and_returns_warning(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, admin, _, booking_room, _ = seed_hotels
    room = booking_room.room
    room.clean_status = "dirty"
    booking_before = {
        "id": booking_room.id,
        "booking_id": booking_room.booking_id,
        "status": booking_room.status,
        "check_in_expected": booking_room.check_in_expected,
        "check_out_expected": booking_room.check_out_expected,
        "deposit": booking_room.room_deposit_amount,
    }
    db.session.commit()
    login_as(client, admin)

    response = client.patch(
        _maintenance_url(hotel, room),
        json={"maintenance": True},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["room"]["status"] == "maintenance"
    assert payload["room"]["clean_status"] == "dirty"
    assert payload["active_booking_count"] == 1
    assert payload["warning"] is True
    assert "không tự" in payload["msg"].lower()
    db.session.refresh(booking_room)
    assert {
        "id": booking_room.id,
        "booking_id": booking_room.booking_id,
        "status": booking_room.status,
        "check_in_expected": booking_room.check_in_expected,
        "check_out_expected": booking_room.check_out_expected,
        "deposit": booking_room.room_deposit_amount,
    } == booking_before


def test_clearing_maintenance_marks_checked_in_room_occupied_and_keeps_clean_status(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, admin, _, booking_room, _ = seed_hotels
    booking_room.status = "checked_in"
    booking_room.room.status = "maintenance"
    booking_room.room.clean_status = "dirty"
    db.session.commit()
    login_as(client, admin)

    response = client.patch(
        _maintenance_url(hotel, booking_room.room),
        json={"maintenance": False},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["room"]["status"] == "occupied"
    assert payload["room"]["clean_status"] == "dirty"
    assert payload["active_booking_count"] == 1
    assert payload["warning"] is True


def test_clearing_maintenance_without_checked_in_room_marks_available(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, admin, _, booking_room, _ = seed_hotels
    booking_room.status = "booked"
    booking_room.room.status = "maintenance"
    booking_room.room.clean_status = "dirty"
    db.session.commit()
    login_as(client, admin)

    response = client.patch(
        _maintenance_url(hotel, booking_room.room),
        json={"maintenance": False},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["room"]["status"] == "available"
    assert payload["room"]["clean_status"] == "dirty"
    assert payload["active_booking_count"] == 1
    assert payload["warning"] is True


def test_maintenance_change_records_transition_audit_and_is_idempotent(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, admin, _, _, _ = seed_hotels
    room = Room(
        hotel_id=hotel.id,
        room_number="103",
        room_type="Standard",
        price_per_night=500000,
        price_initial_block=300000,
        initial_hours=2,
        price_next_hour=50000,
    )
    db.session.add(room)
    db.session.commit()
    login_as(client, admin)

    enabled = client.patch(
        _maintenance_url(hotel, room),
        json={"maintenance": True},
    )
    repeated = client.patch(
        _maintenance_url(hotel, room),
        json={"maintenance": True},
    )
    cleared = client.patch(
        _maintenance_url(hotel, room),
        json={"maintenance": False},
    )

    assert enabled.status_code == repeated.status_code == cleared.status_code == 200
    events = AuditEvent.query.filter_by(
        hotel_id=hotel.id,
        entity_type="room",
        entity_id=room.id,
    ).order_by(AuditEvent.id.asc()).all()
    assert [event.action for event in events] == [
        "set_room_maintenance",
        "clear_room_maintenance",
    ]
    assert events[0].before_data["status"] == "available"
    assert events[0].after_data["status"] == "maintenance"
    assert events[1].before_data["status"] == "maintenance"
    assert events[1].after_data["status"] == "available"


def test_maintenance_state_keeps_existing_search_and_booking_blocks(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, admin, _, booking_room, _ = seed_hotels
    booking_room.status = "cancelled"
    booking_room.room.status = "maintenance"
    db.session.commit()
    login_as(client, admin)

    search_response = client.post(
        f"/{hotel.slug}/rooms/api/rooms/search",
        json={"check_in": "2030-01-01", "check_out": "2030-01-02"},
    )
    booking_response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/create",
        json={
            "room_number": booking_room.room.room_number,
            "check_in": "2030-01-01T14:00",
            "check_out": "2030-01-02T12:00",
            "rental_type": "daily",
            "deposit": 250000,
            "name": "Khách bảo trì",
            "phone": "0900000000",
        },
    )

    assert search_response.status_code == 200
    room_numbers = [
        room["number"]
        for rooms in search_response.get_json()["data"].values()
        for room in rooms
    ]
    assert booking_room.room.room_number not in room_numbers
    assert booking_response.status_code == 200
    assert booking_response.get_json()["success"] is False
    assert "bảo trì" in booking_response.get_json()["msg"].lower()
