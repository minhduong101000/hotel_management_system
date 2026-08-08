import pytest

from extensions import db
from models import AuditEvent, Room, User
from services import audit_service


def test_hotel_admin_creates_room_in_current_tenant(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/rooms/api/settings",
        json={
            "room_number": " 201 ",
            "room_type": " Deluxe ",
            "price_per_night": 850000,
            "price_initial_block": 500000,
            "initial_hours": 3,
            "price_next_hour": 120000,
            "maintenance": False,
        },
    )

    assert response.status_code == 201
    assert response.get_json() == {
        "success": True,
        "room": {
            "id": Room.query.filter_by(hotel_id=hotel.id, room_number="201").one().id,
            "room_number": "201",
            "room_type": "Deluxe",
            "price_per_night": 850000.0,
            "price_initial_block": 500000.0,
            "initial_hours": 3,
            "price_next_hour": 120000.0,
            "status": "available",
            "clean_status": "cleaned",
            "active_booking_count": 0,
        },
    }
    created = Room.query.filter_by(hotel_id=hotel.id, room_number="201").one()
    assert created.room_type == "Deluxe"
    assert created.hotel_id == hotel.id
    assert created.clean_status == "cleaned"
    assert db.session.query(Room).filter_by(hotel_id=hotel.id).count() == 2


def test_staff_cannot_create_room_configuration(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, _, _, _, _ = seed_hotels
    staff = User(username="room_create_staff", role="staff", hotel_id=hotel.id)
    staff.set_password("correct-password")
    db.session.add(staff)
    db.session.commit()
    login_as(client, staff)

    response = client.post(
        f"/{hotel.slug}/rooms/api/settings",
        json={
            "room_number": "202",
            "room_type": "Standard",
            "price_per_night": 500000,
            "price_initial_block": 300000,
            "initial_hours": 2,
            "price_next_hour": 50000,
        },
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "success": False,
        "error_code": "forbidden",
        "msg": "Bạn không có quyền quản lý cấu trúc phòng.",
    }
    assert Room.query.filter_by(hotel_id=hotel.id, room_number="202").first() is None


def test_master_admin_creates_room_in_selected_tenant(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, _, master_admin, _, _ = seed_hotels
    login_as(client, master_admin)

    response = client.post(
        f"/{hotel.slug}/rooms/api/settings",
        json={
            "room_number": "206",
            "room_type": "Standard",
            "price_per_night": 500000,
            "price_initial_block": 300000,
            "initial_hours": 2,
            "price_next_hour": 50000,
        },
    )

    assert response.status_code == 201
    assert Room.query.filter_by(hotel_id=hotel.id, room_number="206").one()


def test_creating_room_records_tenant_scoped_audit_snapshot(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/rooms/api/settings",
        json={
            "room_number": "203",
            "room_type": "Suite",
            "price_per_night": 1200000,
            "price_initial_block": 700000,
            "initial_hours": 4,
            "price_next_hour": 150000,
            "maintenance": True,
        },
    )

    room_id = response.get_json()["room"]["id"]
    event = AuditEvent.query.filter_by(
        hotel_id=hotel.id,
        action="create_room",
        entity_type="room",
        entity_id=room_id,
    ).one()

    assert response.status_code == 201
    assert event.actor_user_id == admin.id
    assert event.before_data is None
    assert event.after_data == {
        "room_number": "203",
        "room_type": "Suite",
        "price_per_night": 1200000.0,
        "price_initial_block": 700000.0,
        "initial_hours": 4,
        "price_next_hour": 150000.0,
        "status": "maintenance",
        "clean_status": "cleaned",
    }


@pytest.mark.parametrize(
    ("payload", "error_field"),
    [
        (
            {
                "room_number": " ",
                "room_type": "Standard",
                "price_per_night": 500000,
                "price_initial_block": 300000,
                "initial_hours": 2,
                "price_next_hour": 50000,
            },
            "room_number",
        ),
        (
            {
                "room_number": "204",
                "room_type": " ",
                "price_per_night": 500000,
                "price_initial_block": 300000,
                "initial_hours": 2,
                "price_next_hour": 50000,
            },
            "room_type",
        ),
        (
            {
                "room_number": "204",
                "room_type": "X" * 21,
                "price_per_night": 500000,
                "price_initial_block": 300000,
                "initial_hours": 2,
                "price_next_hour": 50000,
            },
            "room_type",
        ),
        (
            {
                "room_number": "12345678901",
                "room_type": "Standard",
                "price_per_night": -1,
                "price_initial_block": 300000,
                "initial_hours": 2,
                "price_next_hour": 50000,
            },
            "price_per_night",
        ),
        (
            {
                "room_number": "204",
                "room_type": "Standard",
                "price_per_night": 500000,
                "price_initial_block": float("inf"),
                "initial_hours": 2,
                "price_next_hour": 50000,
            },
            "price_initial_block",
        ),
        (
            {
                "room_number": "204",
                "room_type": "Standard",
                "price_per_night": 500000,
                "price_initial_block": 300000,
                "initial_hours": 2.5,
                "price_next_hour": 50000,
            },
            "initial_hours",
        ),
        (
            {
                "room_number": "204",
                "room_type": "Standard",
                "price_per_night": float("nan"),
                "price_initial_block": 300000,
                "initial_hours": 2,
                "price_next_hour": 50000,
            },
            "price_per_night",
        ),
        (
            {
                "room_number": "204",
                "room_type": "Standard",
                "price_per_night": 500000,
                "price_initial_block": 300000,
                "initial_hours": 2,
                "price_next_hour": None,
            },
            "price_next_hour",
        ),
        (
            {
                "room_number": "204",
                "room_type": "Standard",
                "price_per_night": 500000,
                "price_initial_block": 300000,
                "initial_hours": 2,
                "price_next_hour": "not-a-number",
            },
            "price_next_hour",
        ),
        (
            {
                "room_number": "204",
                "room_type": "Standard",
                "price_per_night": 500000,
                "price_initial_block": 300000,
                "initial_hours": 2,
                "price_next_hour": 50000,
                "maintenance": "yes",
            },
            "maintenance",
        ),
    ],
)
def test_create_room_rejects_invalid_configuration(
    client,
    seed_hotels,
    login_as,
    payload,
    error_field,
):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    response = client.post(f"/{hotel.slug}/rooms/api/settings", json=payload)

    assert response.status_code == 400
    assert response.get_json()["success"] is False
    assert response.get_json()["error_code"] == "validation_error"
    assert error_field in response.get_json()["errors"]
    assert Room.query.filter_by(hotel_id=hotel.id).count() == 1
    assert AuditEvent.query.filter_by(hotel_id=hotel.id, action="create_room").count() == 0


def test_create_room_rejects_duplicate_number_only_within_current_tenant(
    client,
    seed_hotels,
    login_as,
):
    hotel_a, hotel_b, admin_a, _, _, _ = seed_hotels
    payload = {
        "room_number": "201",
        "room_type": "Standard",
        "price_per_night": 500000,
        "price_initial_block": 300000,
        "initial_hours": 2,
        "price_next_hour": 50000,
    }
    login_as(client, admin_a)
    first = client.post(f"/{hotel_a.slug}/rooms/api/settings", json=payload)
    duplicate = client.post(f"/{hotel_a.slug}/rooms/api/settings", json=payload)

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.get_json() == {
        "success": False,
        "error_code": "room_number_conflict",
        "msg": "Số phòng đã tồn tại trong khách sạn này.",
    }

    admin_b = User.query.filter_by(hotel_id=hotel_b.id, username="admin_b").one()
    client.get(f"/{hotel_a.slug}/logout")
    login_as(client, admin_b)
    other_tenant = client.post(f"/{hotel_b.slug}/rooms/api/settings", json=payload)

    assert other_tenant.status_code == 201
    assert Room.query.filter_by(hotel_id=hotel_b.id, room_number="201").count() == 1


def test_create_room_uses_current_tenant_even_when_payload_has_hotel_id(
    client,
    seed_hotels,
    login_as,
):
    hotel_a, hotel_b, admin_a, _, _, _ = seed_hotels
    login_as(client, admin_a)

    response = client.post(
        f"/{hotel_a.slug}/rooms/api/settings",
        json={
            "hotel_id": hotel_b.id,
            "room_number": "205",
            "room_type": "Standard",
            "price_per_night": 500000,
            "price_initial_block": 300000,
            "initial_hours": 2,
            "price_next_hour": 50000,
            "status": "occupied",
        },
    )

    assert response.status_code == 201
    created = Room.query.filter_by(room_number="205").one()
    assert created.hotel_id == hotel_a.id
    assert created.status == "available"


def test_create_room_rolls_back_if_audit_recording_fails(
    client,
    seed_hotels,
    login_as,
    monkeypatch,
):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    def fail_record_event(**_kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(audit_service, "record_event", fail_record_event)

    with pytest.raises(RuntimeError, match="audit unavailable"):
        client.post(
            f"/{hotel.slug}/rooms/api/settings",
            json={
                "room_number": "207",
                "room_type": "Standard",
                "price_per_night": 500000,
                "price_initial_block": 300000,
                "initial_hours": 2,
                "price_next_hour": 50000,
            },
        )

    assert Room.query.filter_by(hotel_id=hotel.id, room_number="207").first() is None
