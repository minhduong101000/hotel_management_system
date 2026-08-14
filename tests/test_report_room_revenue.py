from datetime import datetime

from extensions import db


def test_revenue_top_rooms_joins_booking_room_to_its_actual_room(
    client, booked_room, login_as
):
    hotel, user, _, booking_room = booked_room
    booking_room.status = "checked_out"
    from services import time_service
    booking_room.check_out_actual = time_service.utc_now_naive()
    booking_room.final_amount = 200000
    db.session.commit()
    login_as(client, user)

    response = client.get(f"/{hotel.slug}/reports/api/reports/revenue?period=today")

    assert response.status_code == 200
    top_rooms = response.json["data"]["top_rooms"]
    assert top_rooms == [{
        "room_number": "102",
        "room_type": "Standard",
        "count": 1,
        "total": 200000.0,
    }]
