from datetime import date, datetime, time, timedelta

from extensions import db
from models.expense import Expense
from models.payment import Payment
from models.room import Room


def test_revenue_report_scopes_every_financial_metric_and_excludes_voided_expense(
    client, seed_hotels, login_as
):
    hotel_a, hotel_b, admin_a, _, room_stay_a, room_stay_b = seed_hotels
    from services import time_service

    now = time_service.utc_now_naive()
    room_stay_a.status = "checked_out"
    room_stay_a.check_out_actual = now
    room_stay_a.final_amount = 100_000
    room_stay_a.booking.status = "completed"
    room_stay_a.booking.completed_at = now
    room_stay_b.status = "checked_out"
    room_stay_b.check_out_actual = now
    room_stay_b.final_amount = 900_000
    room_stay_b.booking.status = "completed"
    room_stay_b.booking.completed_at = now
    db.session.add_all(
        [
            Payment(
                hotel_id=hotel_a.id,
                booking_id=room_stay_a.booking_id,
                amount=70_000,
                created_at=now,
            ),
            Payment(
                hotel_id=hotel_b.id,
                booking_id=room_stay_b.booking_id,
                amount=800_000,
                created_at=now,
            ),
            Expense(
                hotel_id=hotel_a.id,
                category="Khác",
                description="Chi phí hợp lệ",
                amount=20_000,
                expense_date=time_service.business_today(),
                created_at=now,
            ),
            Expense(
                hotel_id=hotel_a.id,
                category="Khác",
                description="Chi phí đã void",
                amount=500_000,
                expense_date=time_service.business_today(),
                created_at=now,
                is_voided=True,
            ),
            Expense(
                hotel_id=hotel_b.id,
                category="Khác",
                description="Chi phí tenant khác",
                amount=700_000,
                expense_date=time_service.business_today(),
                created_at=now,
            ),
        ]
    )
    db.session.commit()
    login_as(client, admin_a)

    response = client.get(
        f"/{hotel_a.slug}/reports/api/reports/revenue?period=today"
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["room_revenue"] == 100_000
    assert data["total_net_payment"] == 70_000
    assert data["total_expenses"] == 20_000
    assert data["net_profit"] == 80_000
    assert data["completed_bookings"] == 1
    assert data["top_rooms"] == [
        {
            "room_number": room_stay_a.room.room_number,
            "room_type": room_stay_a.room.room_type,
            "count": 1,
            "total": 100_000,
        }
    ]


def test_profit_and_loss_uses_expense_date_instead_of_record_creation_time(
    client, seed_hotels, login_as
):
    from services import time_service

    hotel, _, admin, _, _, _ = seed_hotels
    # expense_date là ngày nghiệp vụ (report lọc theo business_today()); created_at
    # chỉ là mốc ghi sổ hệ thống (UTC-naive) và cố tình lệch để chứng minh report
    # KHÔNG dùng created_at để lọc.
    business_today = time_service.business_today()
    now = time_service.utc_now_naive()
    db.session.add_all(
        [
            Expense(
                hotel_id=hotel.id,
                category="Khác",
                description="Ghi sổ hôm nay",
                amount=30_000,
                expense_date=business_today,
                created_at=now - timedelta(days=30),
            ),
            Expense(
                hotel_id=hotel.id,
                category="Khác",
                description="Ghi sổ tháng trước",
                amount=90_000,
                expense_date=business_today - timedelta(days=30),
                created_at=now,
            ),
        ]
    )
    db.session.commit()
    login_as(client, admin)

    response = client.get(
        f"/{hotel.slug}/reports/api/reports/revenue?period=today"
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["total_expenses"] == 30_000


def test_occupancy_counts_at_most_one_room_night_per_room_per_calendar_day(
    client, seed_hotels, login_as
):
    hotel, _, admin, _, booking_room, _ = seed_hotels
    second_room = Room(
        hotel_id=hotel.id,
        room_number="102",
        room_type="Standard",
        price_per_night=500_000,
        price_initial_block=300_000,
        initial_hours=2,
    )
    db.session.add(second_room)
    stay_day = date.today()
    booking_room.status = "checked_out"
    booking_room.check_in_actual = datetime.combine(stay_day, time(10, 0))
    booking_room.check_out_actual = datetime.combine(stay_day, time(11, 0))
    db.session.commit()
    login_as(client, admin)

    response = client.get(
        f"/{hotel.slug}/reports/api/reports/revenue"
        f"?period=custom&start={stay_day.isoformat()}&end={stay_day.isoformat()}"
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["occupancy_rate"] == 50.0
    assert data["chart"][0]["occupancy_rate"] == 50.0
