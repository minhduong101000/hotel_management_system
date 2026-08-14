from extensions import db
from models.audit_event import AuditEvent
from models.business_operation import BusinessOperation
from models.payment import Payment


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
    assert booking_room_a.booking.status == "confirmed"


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
    assert booking_room_a.booking.status == "cancelled"


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
    assert BusinessOperation.query.count() == 0


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
def test_repeated_cancellation_is_idempotent_without_refund(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.booking.prepaid_amount = 100000
    booking_room.room_deposit_amount = 100000
    booking_room.room_deposit_original = 100000
    login_as(client, user)
    payload = {"booking_room_id": booking_room.id, "reason": "Khách đổi kế hoạch"}

    first_response = client.post(f"/{hotel.slug}/timeline/api/bookings/cancel", json=payload)
    second_response = client.post(f"/{hotel.slug}/timeline/api/bookings/cancel", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json == first_response.json
    assert Payment.query.filter_by(booking_id=booking_room.booking_id, payment_type="refund").count() == 0
    operation = BusinessOperation.query.one()
    assert operation.operation_key == f"cancel:booking_room:{booking_room.id}"
    assert operation.status == "completed"
    assert operation.result_snapshot == first_response.json


def test_cancel_booking_ignores_client_refund_parameters(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.booking.prepaid_amount = 100000
    booking_room.room_deposit_amount = 100000
    booking_room.room_deposit_original = 100000
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/cancel",
        json={
            "booking_room_id": booking_room.id,
            "reason": "Bão lớn",
            "refund_percent": 100,
            "is_force_majeure": True,
        },
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    data = response.json["data"]
    assert float(data["refund_amount"]) == 0
    assert "refund_percent" not in data
    assert float(data["unrefunded_credit"]) == 100000.0
    assert Payment.query.filter_by(payment_type="refund").count() == 0
    assert booking_room.status == "cancelled"
    assert float(booking_room.cancellation_refund_percent or 0) == 0


def test_cancelling_last_booked_room_completes_booking_with_checked_out_room(
    client,
    booked_room,
    login_as,
):
    hotel, user, checked_out_room, booked_booking_room = booked_room
    checked_out_room.status = "checked_out"
    checked_out_room.final_amount = 400000
    checked_out_room.booking.status = "confirmed"
    db.session.commit()
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/cancel",
        json={
            "booking_room_id": booked_booking_room.id,
            "refund_percent": 0,
            "reason": "Khách hủy phòng còn lại",
        },
    )

    assert response.status_code == 200
    assert booked_booking_room.status == "cancelled"
    assert checked_out_room.booking.status == "completed"
    assert checked_out_room.booking.payment_status == "paid"


def test_booking_and_booking_room_cancellation_keys_do_not_collide(
    client,
    booked_room,
    login_as,
):
    hotel, user, first_room, second_room = booked_room
    login_as(client, user)

    room_response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/cancel",
        json={
            "booking_room_id": first_room.id,
            "refund_percent": 0,
            "reason": "Hủy phòng thứ nhất",
        },
    )
    booking_response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/cancel",
        json={
            "booking_id": first_room.booking_id,
            "refund_percent": 0,
            "reason": "Hủy phần còn lại của đơn",
        },
    )

    assert room_response.status_code == 200
    assert booking_response.status_code == 200
    assert {
        operation.operation_key
        for operation in BusinessOperation.query.order_by(BusinessOperation.id).all()
    } == {
        f"cancel:booking_room:{first_room.id}",
        f"cancel:booking:{first_room.booking_id}",
    }
    assert second_room.status == "cancelled"
