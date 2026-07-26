from datetime import datetime

from extensions import db
from models.audit_event import AuditEvent
from models.inventory_item import InventoryItem
from models.price_rule import PriceRule
from models import Customer


def test_checkout_creates_tenant_scoped_audit_event(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.status = "checked_in"
    booking_room.check_in_actual = datetime.now()
    booking_room.room.status = "occupied"
    db.session.commit()
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/bookings/api/rooms/checkout",
        json={
            "number": booking_room.room.room_number,
            "booking_room_id": booking_room.id,
            "booking_id": booking_room.booking_id,
            "amount": 100000,
        },
    )

    assert response.status_code == 200
    event = AuditEvent.query.one()
    assert event.hotel_id == hotel.id
    assert event.actor_user_id == user.id
    assert event.action == "checkout"
    assert event.entity_type == "booking_room"
    assert event.entity_id == booking_room.id
    assert event.operation_key == f"checkout:{booking_room.id}"


def test_restock_creates_audit_event(client, seed_hotels, login_as):
    hotel, _, user, _, _, _ = seed_hotels
    item = InventoryItem(hotel_id=hotel.id, code="NUOC", name="Nước", quantity=5)
    db.session.add(item)
    db.session.commit()
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/warehouse/api/warehouse/{item.id}/restock",
        json={"quantity": 3},
    )

    assert response.status_code == 200
    event = AuditEvent.query.one()
    assert event.action == "restock_inventory"
    assert event.entity_type == "inventory_item"
    assert event.entity_id == item.id
    assert event.before_data == {"quantity": 5}
    assert event.after_data == {"quantity": 8}


def test_delete_inventory_records_the_deleted_snapshot(client, seed_hotels, login_as):
    hotel, _, user, _, _, _ = seed_hotels
    item = InventoryItem(hotel_id=hotel.id, code="KHAN", name="Khăn", quantity=4)
    db.session.add(item)
    db.session.commit()
    login_as(client, user)

    response = client.delete(f"/{hotel.slug}/warehouse/api/warehouse/{item.id}")

    assert response.status_code == 200
    event = AuditEvent.query.one()
    assert event.action == "delete_inventory"
    assert event.before_data == {"code": "KHAN", "name": "Khăn", "quantity": 4}
    assert event.after_data is None


def test_update_inventory_records_before_and_after_snapshot(client, seed_hotels, login_as):
    hotel, _, user, _, _, _ = seed_hotels
    item = InventoryItem(hotel_id=hotel.id, code="NUOC", name="Nước", quantity=5, price=10000)
    db.session.add(item)
    db.session.commit()
    login_as(client, user)

    response = client.put(
        f"/{hotel.slug}/warehouse/api/warehouse/{item.id}",
        json={"name": "Nước suối", "quantity": 9, "price": 12000},
    )

    assert response.status_code == 200
    event = AuditEvent.query.one()
    assert event.action == "update_inventory"
    assert event.before_data["quantity"] == 5
    assert event.before_data["price"] == 10000.0
    assert event.after_data["name"] == "Nước suối"
    assert event.after_data["quantity"] == 9
    assert event.after_data["price"] == 12000.0


def test_update_base_room_price_creates_audit_event(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/prices/api/prices/update-base",
        json={
            "id": booking_room.room_id,
            "price_daily": 650000,
            "price_initial": 350000,
            "price_next": 100000,
        },
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    event = AuditEvent.query.one()
    assert event.action == "update_base_price"
    assert event.entity_type == "room"
    assert event.entity_id == booking_room.room_id
    assert event.before_data["price_daily"] == 500000.0
    assert event.after_data["price_daily"] == 650000.0


def test_delete_price_rule_records_audit_snapshot(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    rule = PriceRule(
        hotel_id=hotel.id,
        name="Cuối tuần",
        room_type=booking_room.room.room_type,
        price_daily=800000,
        priority=5,
        is_active=True,
    )
    db.session.add(rule)
    db.session.commit()
    login_as(client, user)

    response = client.delete(f"/{hotel.slug}/prices/api/prices/delete-rule/{rule.id}")

    assert response.status_code == 200
    event = AuditEvent.query.one()
    assert event.action == "delete_price_rule"
    assert event.entity_type == "price_rule"
    assert event.entity_id == rule.id
    assert event.before_data["name"] == "Cuối tuần"
    assert event.before_data["price_daily"] == 800000.0


def test_update_price_rule_records_before_and_after_snapshot(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    rule = PriceRule(
        hotel_id=hotel.id,
        name="Ngày thường",
        room_type=booking_room.room.room_type,
        price_daily=600000,
        priority=1,
        is_active=True,
    )
    db.session.add(rule)
    db.session.commit()
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/prices/api/prices/save-rule",
        json={
            "id": rule.id,
            "name": "Lễ",
            "room_type": booking_room.room.room_type,
            "priority": 10,
            "price_daily": 900000,
        },
    )

    assert response.status_code == 200
    event = AuditEvent.query.one()
    assert event.action == "update_price_rule"
    assert event.before_data["name"] == "Ngày thường"
    assert event.after_data["name"] == "Lễ"
    assert event.after_data["price_daily"] == 900000.0


def test_create_price_rule_records_audit_event(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/prices/api/prices/save-rule",
        json={
            "name": "Mùa cao điểm",
            "room_type": booking_room.room.room_type,
            "priority": 8,
            "price_daily": 850000,
        },
    )

    assert response.status_code == 200
    event = AuditEvent.query.one()
    assert event.action == "create_price_rule"
    assert event.entity_type == "price_rule"
    assert event.after_data["name"] == "Mùa cao điểm"
    assert event.after_data["price_daily"] == 850000.0


def test_delete_customer_records_audit_snapshot(client, seed_hotels, login_as):
    hotel, _, user, _, _, _ = seed_hotels
    customer = Customer(hotel_id=hotel.id, name="Khách xóa", phone="0900999999")
    db.session.add(customer)
    db.session.commit()
    login_as(client, user)

    response = client.delete(f"/{hotel.slug}/customers/api/customers/{customer.id}")

    assert response.status_code == 200
    event = AuditEvent.query.one()
    assert event.action == "delete_customer"
    assert event.entity_type == "customer"
    assert event.entity_id == customer.id
    assert event.before_data == {"name": "Khách xóa", "phone": "0900999999"}
