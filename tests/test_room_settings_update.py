from datetime import datetime

import pytest

from extensions import db
from models import AuditEvent, Room, User
from services import booking_quote_service


def _room_payload(**overrides):
    payload = {
        "room_number": "201",
        "room_type": "Deluxe",
        "price_per_night": 750000,
        "price_initial_block": 450000,
        "initial_hours": 3,
        "price_next_hour": 90000,
    }
    payload.update(overrides)
    return payload


def test_hotel_admin_updates_room_structure_rates_and_audit(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, admin, _, booking_room, _ = seed_hotels
    room = booking_room.room
    booking_room.price_breakdown_snapshot = [
        {"business_date": "2030-01-01", "amount": 500000.0}
    ]
    db.session.commit()
    login_as(client, admin)

    response = client.put(
        f"/{hotel.slug}/rooms/api/settings/{room.id}",
        json=_room_payload(status="occupied", clean_status="dirty"),
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert response.get_json()["room"] == {
        "id": room.id,
        "room_number": "201",
        "room_type": "Deluxe",
        "price_per_night": 750000.0,
        "price_initial_block": 450000.0,
        "initial_hours": 3,
        "price_next_hour": 90000.0,
        "status": "available",
        "clean_status": "cleaned",
        "active_booking_count": 1,
    }
    db.session.refresh(room)
    assert room.status == "available"
    assert room.clean_status == "cleaned"
    assert booking_room.price_breakdown_snapshot == [
        {"business_date": "2030-01-01", "amount": 500000.0}
    ]

    event = AuditEvent.query.filter_by(
        hotel_id=hotel.id,
        action="update_room",
        entity_type="room",
        entity_id=room.id,
    ).one()
    assert event.actor_user_id == admin.id
    assert event.before_data == {
        "room_number": "101",
        "room_type": "Standard",
        "price_per_night": 500000.0,
        "price_initial_block": 300000.0,
        "initial_hours": 2,
        "price_next_hour": 50000.0,
        "status": "available",
        "clean_status": "cleaned",
    }
    assert event.after_data == {
        "room_number": "201",
        "room_type": "Deluxe",
        "price_per_night": 750000.0,
        "price_initial_block": 450000.0,
        "initial_hours": 3,
        "price_next_hour": 90000.0,
        "status": "available",
        "clean_status": "cleaned",
    }


def test_master_admin_updates_room_in_selected_tenant(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, _, master_admin, booking_room, _ = seed_hotels
    login_as(client, master_admin)

    response = client.put(
        f"/{hotel.slug}/rooms/api/settings/{booking_room.room_id}",
        json=_room_payload(room_number="202"),
    )

    assert response.status_code == 200
    assert db.session.get(Room, booking_room.room_id).room_number == "202"


def test_staff_cannot_update_room_structure(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, _, _, booking_room, _ = seed_hotels
    staff = User(username="room_update_staff", role="staff", hotel_id=hotel.id)
    staff.set_password("correct-password")
    db.session.add(staff)
    db.session.commit()
    login_as(client, staff)

    response = client.put(
        f"/{hotel.slug}/rooms/api/settings/{booking_room.room_id}",
        json=_room_payload(),
    )

    assert response.status_code == 403
    assert response.get_json()["error_code"] == "forbidden"
    assert db.session.get(Room, booking_room.room_id).room_number == "101"


def test_update_room_does_not_disclose_other_tenant_room(
    client,
    seed_hotels,
    login_as,
):
    hotel_a, _, admin_a, _, _, booking_room_b = seed_hotels
    login_as(client, admin_a)

    response = client.put(
        f"/{hotel_a.slug}/rooms/api/settings/{booking_room_b.room_id}",
        json=_room_payload(),
    )

    assert response.status_code == 404


def test_update_room_duplicate_number_rolls_back_without_audit(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, admin, _, booking_room, _ = seed_hotels
    second_room = Room(
        hotel_id=hotel.id,
        room_number="102",
        room_type="Standard",
        price_per_night=600000,
        price_initial_block=350000,
        initial_hours=2,
        price_next_hour=50000,
    )
    db.session.add(second_room)
    db.session.commit()
    login_as(client, admin)

    response = client.put(
        f"/{hotel.slug}/rooms/api/settings/{booking_room.room_id}",
        json=_room_payload(room_number="102"),
    )

    assert response.status_code == 409
    assert response.get_json()["error_code"] == "room_number_conflict"
    db.session.refresh(booking_room.room)
    assert booking_room.room.room_number == "101"
    assert booking_room.room.room_type == "Standard"
    assert booking_room.room.price_per_night == 500000
    assert AuditEvent.query.filter_by(
        hotel_id=hotel.id,
        action="update_room",
    ).count() == 0


def test_update_room_reuses_validation_contract_without_audit(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, admin, _, booking_room, _ = seed_hotels
    login_as(client, admin)

    response = client.put(
        f"/{hotel.slug}/rooms/api/settings/{booking_room.room_id}",
        json=_room_payload(price_per_night=0),
    )

    assert response.status_code == 400
    assert response.get_json()["error_code"] == "validation_error"
    assert "price_per_night" in response.get_json()["errors"]
    assert AuditEvent.query.filter_by(
        hotel_id=hotel.id,
        action="update_room",
    ).count() == 0


def test_admin_updates_default_rates_with_canonical_fields_staff_forbidden(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, admin, _, booking_room, _ = seed_hotels
    room = booking_room.room
    staff = User(username="rate_update_staff", role="staff", hotel_id=hotel.id)
    staff.set_password("correct-password")
    db.session.add(staff)
    db.session.commit()

    # Staff khong duoc sua gia (chinh sach 14-08)
    login_as(client, staff)
    staff_response = client.post(
        f"/{hotel.slug}/prices/api/prices/update-base",
        json={"id": room.id, "price_per_night": 1},
    )
    assert staff_response.status_code == 403
    client.get(f"/{hotel.slug}/logout")

    login_as(client, admin)
    response = client.post(
        f"/{hotel.slug}/prices/api/prices/update-base",
        json={
            "id": room.id,
            "price_per_night": 680000,
            "price_initial_block": 400000,
            "initial_hours": 4,
            "price_next_hour": 80000,
            "room_number": "hacked",
            "room_type": "Suite",
            "status": "maintenance",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    db.session.refresh(room)
    assert (
        room.price_per_night,
        room.price_initial_block,
        room.initial_hours,
        float(room.price_next_hour),
    ) == (680000, 400000, 4, 80000.0)
    assert room.room_number == "101"
    assert room.room_type == "Standard"
    assert room.status == "available"

    event = AuditEvent.query.filter_by(
        hotel_id=hotel.id,
        action="update_base_price",
        entity_type="room",
        entity_id=room.id,
    ).one()
    assert event.after_data["initial_hours"] == 4
    assert event.after_data["price_next_hour"] == 80000.0


@pytest.mark.parametrize(
    "invalid_price",
    [0, -1, float("nan"), float("inf")],
)
def test_price_only_update_reuses_validation_contract(
    client,
    seed_hotels,
    login_as,
    invalid_price,
):
    hotel, _, admin, _, booking_room, _ = seed_hotels
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/prices/api/prices/update-base",
        json={
            "id": booking_room.room_id,
            "price_per_night": invalid_price,
            "price_initial_block": 300000,
            "initial_hours": 2,
            "price_next_hour": 50000,
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error_code"] == "validation_error"
    assert "price_per_night" in response.get_json()["errors"]
    assert AuditEvent.query.filter_by(
        hotel_id=hotel.id,
        action="update_base_price",
    ).count() == 0


def test_default_rate_update_changes_new_quote_but_not_existing_snapshot(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, admin, _, booking_room, _ = seed_hotels
    booking_room.status = "checked_in"
    # check_in_actual là UTC-naive; 07:00 UTC = 14:00 VN.
    booking_room.check_in_actual = datetime(2030, 1, 1, 7, 0)
    # check_out_expected là giờ nghiệp vụ VN naive, không quy đổi.
    booking_room.check_out_expected = datetime(2030, 1, 2, 12, 0)
    booking_room.price_breakdown_snapshot = [
        {"business_date": "2030-01-01", "amount": 500000.0}
    ]
    db.session.commit()
    login_as(client, admin)

    response = client.put(
        f"/{hotel.slug}/rooms/api/settings/{booking_room.room_id}",
        json=_room_payload(),
    )

    assert response.status_code == 200
    new_quote = booking_quote_service.build_new_booking_quote(
        [booking_room.room],
        check_in=datetime(2030, 2, 1, 14, 0),
        check_out=datetime(2030, 2, 2, 12, 0),
    )
    # checkout_at là mốc hệ thống UTC-naive; 05:00 UTC = 12:00 VN.
    existing_quote = booking_quote_service.build_checkout_quote(
        booking_room,
        checkout_at=datetime(2030, 1, 2, 5, 0),
        include_tax=False,
    )

    assert new_quote["room_subtotal"] == "750000.00"
    assert existing_quote["room_subtotal"] == "500000.00"
