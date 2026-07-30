from datetime import datetime
from decimal import Decimal

import pytest

from models import Payment
from services import booking_state_service


def test_booking_state_is_derived_deterministically_from_all_rooms(booked_room):
    _, _, first_room, second_room = booked_room
    booking = first_room.booking
    changed_at = datetime(2026, 7, 30, 9, 0)
    first_room.final_amount = Decimal("400000")
    second_room.final_amount = Decimal("100000")

    first_room.status = "booked"
    second_room.status = "cancelled"
    booking_state_service.aggregate_booking_state(booking, changed_at=changed_at)
    assert booking.status == "confirmed"

    first_room.status = "checked_in"
    booking_state_service.aggregate_booking_state(booking, changed_at=changed_at)
    assert booking.status == "checked_in"

    first_room.status = "checked_out"
    booking_state_service.aggregate_booking_state(booking, changed_at=changed_at)
    assert booking.status == "completed"
    assert booking.payment_status == "paid"

    first_room.status = "cancelled"
    booking_state_service.aggregate_booking_state(booking, changed_at=changed_at)
    assert booking.status == "cancelled"
    assert booking.total_amount == Decimal("500000")
    assert booking.updated_at == changed_at


def test_checkin_transition_synchronizes_parent_and_physical_room(booked_room):
    _, _, first_room, second_room = booked_room
    checked_in_at = datetime(2026, 7, 30, 10, 0)

    booking_state_service.check_in_room(
        second_room,
        checked_in_at=checked_in_at,
    )

    assert first_room.status == "booked"
    assert second_room.status == "checked_in"
    assert second_room.check_in_actual == checked_in_at
    assert second_room.room.status == "occupied"
    assert second_room.booking.status == "checked_in"


def test_batch_cancellation_validates_every_room_before_mutation(booked_room):
    _, _, first_room, second_room = booked_room
    first_room.room.status = "available"
    second_room.status = "checked_in"
    second_room.room.status = "occupied"
    cancelled_at = datetime(2026, 7, 30, 11, 0)

    with pytest.raises(booking_state_service.InvalidBookingTransition):
        booking_state_service.cancel_rooms(
            [first_room, second_room],
            cancelled_at=cancelled_at,
        )

    assert first_room.status == "booked"
    assert first_room.check_out_actual is None
    assert first_room.room.status == "available"
    assert second_room.status == "checked_in"
    assert second_room.check_out_actual is None
    assert second_room.room.status == "occupied"


def test_invalid_single_transition_does_not_mutate_room(booked_room):
    _, _, first_room, _ = booked_room
    first_room.status = "cancelled"
    original_room_status = first_room.room.status

    with pytest.raises(booking_state_service.InvalidBookingTransition):
        booking_state_service.check_in_room(
            first_room,
            checked_in_at=datetime(2026, 7, 30, 12, 0),
        )

    assert first_room.status == "cancelled"
    assert first_room.check_in_actual is None
    assert first_room.room.status == original_room_status


def test_reschedule_guard_accepts_only_booked_room(booked_room):
    _, _, first_room, _ = booked_room

    booking_state_service.ensure_reschedulable(first_room)
    first_room.status = "checked_in"

    with pytest.raises(booking_state_service.InvalidBookingTransition):
        booking_state_service.ensure_reschedulable(first_room)


@pytest.mark.parametrize("requested_status", ["checked_in", "cancelled"])
def test_generic_booking_update_cannot_bypass_transition_workflows(
    client,
    seed_hotels,
    login_as,
    requested_status,
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    original_deposit = booking_room.booking.prepaid_amount
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json={
            "booking_id": booking_room.booking_id,
            "booking_room_id": booking_room.id,
            "room_id": booking_room.room_id,
            "status": requested_status,
            "deposit": 100000,
        },
    )

    assert response.status_code == 409
    assert response.json["error_code"] == "state_transition_endpoint_required"
    assert booking_room.status == "booked"
    assert booking_room.booking.prepaid_amount == original_deposit
    assert Payment.query.count() == 0
