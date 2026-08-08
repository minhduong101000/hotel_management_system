from datetime import date, datetime

from extensions import db
from models import PriceRule, Room, User
from services.pricing_service import get_effective_room_prices


def _rule_payload(**overrides):
    payload = {
        "name": "Cuối tuần",
        "room_type": "Standard",
        "priority": 5,
        "start_date": "2030-01-01",
        "end_date": "2030-01-31",
        "days_of_week": [0, 1, 2],
        "price_daily": 750000,
    }
    payload.update(overrides)
    return payload


def test_price_rules_contract_returns_only_current_tenant_rules_and_types(
    client,
    seed_hotels,
    login_as,
):
    hotel_a, hotel_b, admin_a, _, booking_room_a, _ = seed_hotels
    db.session.add_all([
        PriceRule(
            hotel_id=hotel_a.id,
            name="Lễ A",
            room_type=booking_room_a.room.room_type,
            priority=10,
            start_date=date(2030, 1, 1),
            end_date=date(2030, 1, 2),
            days_of_week="0,1",
            is_active=True,
            price_daily=900000,
        ),
        PriceRule(
            hotel_id=hotel_b.id,
            name="Lễ B",
            room_type="Suite",
            priority=20,
            is_active=False,
            price_daily=1200000,
        ),
    ])
    db.session.commit()
    login_as(client, admin_a)

    response = client.get(f"/{hotel_a.slug}/prices/api/prices/rules")

    assert response.status_code == 200
    assert response.get_json() == {
        "room_types": ["Standard"],
        "rules": [
            {
                "id": PriceRule.query.filter_by(hotel_id=hotel_a.id).one().id,
                "name": "Lễ A",
                "room_type": "Standard",
                "priority": 10,
                "start_date": "2030-01-01",
                "end_date": "2030-01-02",
                "days_of_week": "0,1",
                "is_active": True,
                "price_daily": 900000.0,
            }
        ],
    }
    rule = response.get_json()["rules"][0]
    assert "price_initial" not in rule
    assert "price_next" not in rule


def test_staff_and_master_can_read_price_rule_contract(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, _, master_admin, _, _ = seed_hotels
    staff = User(username="rule_reader_staff", role="staff", hotel_id=hotel.id)
    staff.set_password("correct-password")
    db.session.add(staff)
    db.session.commit()
    login_as(client, staff)

    staff_response = client.get(f"/{hotel.slug}/prices/api/prices/rules")

    assert staff_response.status_code == 200
    client.get(f"/{hotel.slug}/logout")
    login_as(client, master_admin)
    master_response = client.get(f"/{hotel.slug}/prices/api/prices/rules")
    assert master_response.status_code == 200


def test_creating_rule_scopes_to_tenant_and_ignores_hourly_payload(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, admin, _, booking_room, _ = seed_hotels
    room = booking_room.room
    before_rates = (
        room.price_per_night,
        room.price_initial_block,
        room.initial_hours,
        room.price_next_hour,
    )
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/prices/api/prices/save-rule",
        json=_rule_payload(
            price_initial=999999,
            price_next=888888,
            price_initial_block=777777,
            price_next_hour=666666,
        ),
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    rule = PriceRule.query.filter_by(hotel_id=hotel.id).one()
    assert rule.price_daily == 750000
    assert rule.hotel_id == hotel.id
    db.session.refresh(room)
    assert (
        room.price_per_night,
        room.price_initial_block,
        room.initial_hours,
        room.price_next_hour,
    ) == before_rates


def test_price_rule_update_and_delete_cannot_cross_tenant(
    client,
    seed_hotels,
    login_as,
):
    hotel_a, hotel_b, admin_a, _, booking_room_a, _ = seed_hotels
    foreign_rule = PriceRule(
        hotel_id=hotel_b.id,
        name="Foreign",
        room_type=booking_room_a.room.room_type,
        priority=1,
        is_active=True,
        price_daily=800000,
    )
    db.session.add(foreign_rule)
    db.session.commit()
    login_as(client, admin_a)

    update_response = client.post(
        f"/{hotel_a.slug}/prices/api/prices/save-rule",
        json=_rule_payload(id=foreign_rule.id, price_daily=999999),
    )
    delete_response = client.delete(
        f"/{hotel_a.slug}/prices/api/prices/delete-rule/{foreign_rule.id}"
    )

    assert update_response.status_code == 404
    assert delete_response.status_code == 404
    db.session.refresh(foreign_rule)
    assert foreign_rule.price_daily == 800000


def test_effective_price_uses_room_defaults_without_matching_rule(
    app,
    seed_hotels,
):
    _, _, _, _, booking_room, _ = seed_hotels
    room = booking_room.room
    room.price_per_night = 650000
    room.price_initial_block = 360000
    room.initial_hours = 3
    room.price_next_hour = 80000
    db.session.commit()

    with app.app_context():
        prices = get_effective_room_prices(room, datetime(2030, 2, 1, 14, 0))

    assert prices == {
        "p_night": 650000.0,
        "p_initial": 360000.0,
        "p_next": 80000.0,
        "initial_hours": 3,
        "is_special": False,
        "rule_name": "Giá niêm yết",
    }


def test_matching_rule_overrides_only_nightly_price_and_honors_priority(
    app,
    seed_hotels,
):
    hotel, _, _, _, booking_room, _ = seed_hotels
    room = booking_room.room
    room.price_per_night = 650000
    room.price_initial_block = 360000
    room.initial_hours = 3
    room.price_next_hour = 80000
    db.session.add_all([
        PriceRule(
            hotel_id=hotel.id,
            name="Ưu tiên thấp",
            room_type=room.room_type,
            priority=1,
            is_active=True,
            price_daily=700000,
        ),
        PriceRule(
            hotel_id=hotel.id,
            name="Ưu tiên cao",
            room_type=room.room_type,
            priority=2,
            is_active=True,
            price_daily=850000,
        ),
    ])
    db.session.commit()

    with app.app_context():
        prices = get_effective_room_prices(room, datetime(2030, 2, 1, 14, 0))

    assert prices == {
        "p_night": 850000.0,
        "p_initial": 360000.0,
        "p_next": 80000.0,
        "initial_hours": 3,
        "is_special": True,
        "rule_name": "Ưu tiên cao",
    }


def test_inactive_out_of_range_and_wrong_weekday_rules_do_not_apply(
    app,
    seed_hotels,
):
    hotel, _, _, _, booking_room, _ = seed_hotels
    room = booking_room.room
    check_at = datetime(2030, 2, 4, 14, 0)  # Monday
    db.session.add_all([
        PriceRule(
            hotel_id=hotel.id,
            name="Không hoạt động",
            room_type=room.room_type,
            priority=10,
            is_active=False,
            price_daily=900000,
        ),
        PriceRule(
            hotel_id=hotel.id,
            name="Ngoài khoảng ngày",
            room_type=room.room_type,
            priority=9,
            start_date=date(2030, 1, 1),
            end_date=date(2030, 1, 2),
            is_active=True,
            price_daily=800000,
        ),
        PriceRule(
            hotel_id=hotel.id,
            name="Sai thứ",
            room_type=room.room_type,
            priority=8,
            days_of_week="1",
            is_active=True,
            price_daily=700000,
        ),
    ])
    db.session.commit()

    with app.app_context():
        prices = get_effective_room_prices(room, check_at)

    assert prices["is_special"] is False
    assert prices["p_night"] == 500000.0


def test_existing_price_page_and_legacy_data_api_stay_available(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    page_response = client.get(f"/{hotel.slug}/prices/admin/price-manager")
    api_response = client.get(f"/{hotel.slug}/prices/api/prices/all-data")

    assert page_response.status_code == 200
    assert api_response.status_code == 200
