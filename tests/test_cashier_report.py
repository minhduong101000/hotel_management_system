from datetime import date, datetime

from extensions import db
from models.expense import Expense
from models.payment import Payment


def test_cashier_scopes_tenant_and_excludes_voided_expense(
    client, seed_hotels, login_as
):
    hotel_a, hotel_b, admin_a, _, room_stay_a, room_stay_b = seed_hotels
    now = datetime.now()
    db.session.add_all(
        [
            Payment(
                hotel_id=hotel_a.id,
                booking_id=room_stay_a.booking_id,
                amount=100_000,
                payment_type="deposit",
                created_at=now,
            ),
            Payment(
                hotel_id=hotel_a.id,
                booking_id=room_stay_a.booking_id,
                amount=-20_000,
                payment_type="refund",
                created_at=now,
            ),
            Payment(
                hotel_id=hotel_b.id,
                booking_id=room_stay_b.booking_id,
                amount=900_000,
                created_at=now,
            ),
            Expense(
                hotel_id=hotel_a.id,
                category="Khác",
                description="Chi tiền hợp lệ",
                amount=30_000,
                expense_date=date.today(),
                created_at=now,
            ),
            Expense(
                hotel_id=hotel_a.id,
                category="Khác",
                description="Chi tiền đã void",
                amount=400_000,
                expense_date=date.today(),
                created_at=now,
                is_voided=True,
            ),
            Expense(
                hotel_id=hotel_b.id,
                category="Khác",
                description="Chi tenant khác",
                amount=700_000,
                expense_date=date.today(),
                created_at=now,
            ),
        ]
    )
    db.session.commit()
    login_as(client, admin_a)

    response = client.get(
        f"/{hotel_a.slug}/cashier/api/reports/cashier?period=today"
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["total_received"] == 100_000
    assert data["total_refunded"] == 20_000
    assert data["total_expense"] == 30_000
    assert data["net_amount"] == 50_000
    assert {record["booking_code"] for record in data["records"]} == {
        room_stay_a.booking.code
    }
