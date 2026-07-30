def test_cancel_booking_room_marks_only_requested_room_cancelled(
    client, booked_room, login_as
):
    hotel, user, booking_room_a, booking_room_b = booked_room
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/cancel",
        json={"booking_room_id": booking_room_a.id, "refund_percent": 0, "reason": "Khách hủy"},
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    assert booking_room_a.status == "cancelled"
    assert booking_room_b.status == "booked"


def test_cancel_booking_room_rejects_another_hotels_room(client, seed_hotels, login_as):
    hotel_a, _, user_a, _, booking_room_a, booking_room_b = seed_hotels
    login_as(client, user_a)

    response = client.post(
        f"/{hotel_a.slug}/timeline/api/bookings/cancel",
        json={"booking_room_id": booking_room_b.id, "refund_percent": 0, "reason": "Khách hủy"},
    )

    assert response.status_code == 404
    assert response.json["success"] is False
    assert booking_room_a.status == "booked"
    assert booking_room_b.status == "booked"


def test_cancel_booking_by_booking_id_cancels_all_active_rooms(client, booked_room, login_as):
    hotel, user, booking_room_a, booking_room_b = booked_room
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/cancel",
        json={"booking_id": booking_room_a.booking_id, "refund_percent": 0, "reason": "Khách hủy"},
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    assert booking_room_a.status == "cancelled"
    assert booking_room_b.status == "cancelled"


def test_cancel_booking_rejects_invalid_id_and_checked_out_room(
    client, seed_hotels, login_as
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    login_as(client, user)

    invalid_response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/cancel",
        json={"booking_room_id": "not-a-number", "refund_percent": 0, "reason": "Khách hủy"},
    )
    booking_room.status = "checked_out"
    checked_out_response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/cancel",
        json={"booking_room_id": booking_room.id, "refund_percent": 0, "reason": "Khách hủy"},
    )

    assert invalid_response.status_code == 400
    assert invalid_response.json["success"] is False
    assert checked_out_response.status_code == 409
    assert checked_out_response.json["success"] is False
    assert booking_room.status == "checked_out"


def test_cancel_booking_rejects_checked_in_room(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.status = "checked_in"
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/cancel",
        json={"booking_room_id": booking_room.id, "refund_percent": 0, "reason": "Khách hủy"},
    )

    assert response.status_code == 409
    assert response.json["success"] is False
    assert booking_room.status == "checked_in"


def test_cancel_booking_requires_a_reason_and_records_audit_event(
    client, seed_hotels, login_as
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    login_as(client, user)

    missing_reason = client.post(
        f"/{hotel.slug}/timeline/api/bookings/cancel",
        json={"booking_room_id": booking_room.id, "refund_percent": 0},
    )
    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/cancel",
        json={
            "booking_room_id": booking_room.id,
            "refund_percent": 0,
            "reason": "Khách thay đổi kế hoạch",
        },
    )

    assert missing_reason.status_code == 400
    assert response.status_code == 200
    event = AuditEvent.query.one()
    assert event.hotel_id == hotel.id
    assert event.actor_user_id == user.id
    assert event.action == "cancel_booking"
    assert event.entity_type == "booking_room"
    assert event.entity_id == booking_room.id
    assert event.after_data["reason"] == "Khách thay đổi kế hoạch"
from models.audit_event import AuditEvent
from models.business_operation import BusinessOperation
from models.payment import Payment


def test_repeated_cancellation_does_not_duplicate_refund_or_operation(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.booking.prepaid_amount = 100000
    booking_room.room_deposit_amount = 100000
    booking_room.room_deposit_original = 100000
    login_as(client, user)
    payload = {"booking_room_id": booking_room.id, "refund_percent": 50, "reason": "Khách đổi kế hoạch"}

    first_response = client.post(f"/{hotel.slug}/timeline/api/bookings/cancel", json=payload)
    second_response = client.post(f"/{hotel.slug}/timeline/api/bookings/cancel", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json == first_response.json
    assert Payment.query.filter_by(booking_id=booking_room.booking_id, payment_type="refund").count() == 1
    operation = BusinessOperation.query.one()
    assert operation.operation_key == f"cancel:booking_room:{booking_room.id}"
    assert operation.status == "completed"
    assert operation.result_snapshot == first_response.json
    payment = Payment.query.filter_by(payment_type="refund").one()
    assert payment.business_operation_id == operation.id
    assert payment.component_key == "refund"
