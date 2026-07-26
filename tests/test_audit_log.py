from datetime import datetime

from extensions import db
from models.audit_event import AuditEvent
from models.inventory_item import InventoryItem
from models.price_rule import PriceRule
from models import Customer
from models.expense import Expense
from models.booking_service import BookingService
from models import Service


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


def test_update_customer_records_before_and_after_snapshot(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    customer = booking_room.booking.customer
    login_as(client, user)

    response = client.put(
        f"/{hotel.slug}/customers/api/customers/{customer.id}",
        json={"name": "Tên mới", "phone": "0900111222", "address": "Hà Nội"},
    )

    assert response.status_code == 200
    event = AuditEvent.query.one()
    assert event.action == "update_customer"
    assert event.before_data["name"] == "Nguyen Van A"
    assert event.after_data["name"] == "Tên mới"


def test_delete_service_records_audit_snapshot(client, seed_hotels, login_as):
    hotel, _, user, _, _, _ = seed_hotels
    service = Service(hotel_id=hotel.id, name="Giặt", price=50000)
    db.session.add(service)
    db.session.commit()
    login_as(client, user)

    response = client.delete(f"/{hotel.slug}/services/api/services/{service.id}")

    assert response.status_code == 200
    event = AuditEvent.query.one()
    assert event.action == "delete_service"
    assert event.before_data == {"name": "Giặt", "price": 50000.0}


def test_update_service_records_audit_snapshot(client, seed_hotels, login_as):
    hotel, _, user, _, _, _ = seed_hotels
    service = Service(hotel_id=hotel.id, name="Nước", price=10000)
    db.session.add(service)
    db.session.commit()
    login_as(client, user)

    response = client.put(
        f"/{hotel.slug}/services/api/services/{service.id}",
        json={"name": "Nước suối", "price": 15000},
    )

    assert response.status_code == 200
    event = AuditEvent.query.one()
    assert event.action == "update_service"
    assert event.before_data == {"name": "Nước", "price": 10000.0}
    assert event.after_data == {"name": "Nước suối", "price": 15000.0}


def test_create_service_records_audit_event(client, seed_hotels, login_as):
    hotel, _, user, _, _, _ = seed_hotels
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/services/api/services",
        json={"name": "Ăn sáng", "price": 150000},
    )

    assert response.status_code == 200
    event = AuditEvent.query.one()
    assert event.action == "create_service"
    assert event.after_data == {"name": "Ăn sáng", "price": 150000.0}


def test_create_booking_records_audit_event(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.check_in_expected = datetime(2030, 1, 1, 14, 0)
    booking_room.check_out_expected = datetime(2030, 1, 2, 12, 0)
    db.session.commit()
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/create",
        json={
            "room_number": booking_room.room.room_number,
            "check_in": "2030-01-02T12:00",
            "check_out": "2030-01-03T12:00",
            "rental_type": "daily",
            "deposit": 250000,
            "name": "Khách mới",
        },
    )

    assert response.status_code == 200
    event = AuditEvent.query.one()
    assert event.hotel_id == hotel.id
    assert event.actor_user_id == user.id
    assert event.action == "create_booking"
    assert event.entity_type == "booking_room"
    assert event.after_data["room_number"] == booking_room.room.room_number
    assert event.after_data["status"] == "booked"


def test_update_timeline_records_audit_event(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.check_in_expected = datetime(2030, 1, 1, 14, 0)
    booking_room.check_out_expected = datetime(2030, 1, 2, 12, 0)
    db.session.commit()
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update_timeline",
        json={
            "id": booking_room.id,
            "start": "2030-01-01T15:00:00",
            "end": "2030-01-02T13:00:00",
        },
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    event = AuditEvent.query.one()
    assert event.action == "update_booking_timeline"
    assert event.entity_id == booking_room.id
    assert event.before_data["check_in_expected"] == "2030-01-01T14:00:00"
    assert event.after_data["check_in_expected"] == "2030-01-01T15:00:00"


def test_clean_room_records_audit_event(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    room = booking_room.room
    room.clean_status = "dirty"
    db.session.commit()
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/rooms/api/rooms/clean",
        json={"number": room.room_number},
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    event = AuditEvent.query.one()
    assert event.action == "clean_room"
    assert event.entity_type == "room"
    assert event.entity_id == room.id
    assert event.before_data == {"status": "available", "clean_status": "dirty"}
    assert event.after_data == {"status": "available", "clean_status": "cleaned"}


def test_create_expense_records_audit_event(client, seed_hotels, login_as):
    hotel, _, user, _, _, _ = seed_hotels
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/expenses/api/expenses",
        json={
            "category": "Sửa chữa",
            "description": "Thay bóng đèn",
            "amount": 120000,
            "expense_date": "2030-01-01",
        },
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    event = AuditEvent.query.one()
    assert event.action == "create_expense"
    assert event.entity_type == "expense"
    assert event.after_data == {
        "category": "Sửa chữa",
        "description": "Thay bóng đèn",
        "amount": 120000.0,
        "expense_date": "2030-01-01",
    }


def test_delete_expense_records_audit_event(client, seed_hotels, login_as):
    hotel, _, user, _, _, _ = seed_hotels
    expense = Expense(
        hotel_id=hotel.id,
        category="Khác",
        description="Chi phí cần xóa",
        amount=50000,
        expense_date=datetime(2030, 1, 2).date(),
        created_by=user.id,
    )
    db.session.add(expense)
    db.session.commit()
    login_as(client, user)

    response = client.delete(f"/{hotel.slug}/expenses/api/expenses/{expense.id}")

    assert response.status_code == 200
    assert response.json["success"] is True
    event = AuditEvent.query.one()
    assert event.action == "delete_expense"
    assert event.entity_id == expense.id
    assert event.before_data == {
        "category": "Khác",
        "description": "Chi phí cần xóa",
        "amount": 50000.0,
        "expense_date": "2030-01-02",
    }


def test_checkin_records_audit_event(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/bookings/api/rooms/checkin",
        json={"booking_room_id": booking_room.id},
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    event = AuditEvent.query.one()
    assert event.action == "checkin"
    assert event.entity_type == "booking_room"
    assert event.entity_id == booking_room.id
    assert event.before_data == {"booking_status": "booked", "room_status": "available"}
    assert event.after_data["booking_status"] == "checked_in"
    assert event.after_data["room_status"] == "occupied"


def test_update_service_quantity_records_audit_event(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    service = Service(hotel_id=hotel.id, name="Nước", price=10000)
    db.session.add(service)
    db.session.flush()
    line_item = BookingService(
        hotel_id=hotel.id,
        booking_id=booking_room.booking_id,
        room_id=booking_room.room_id,
        service_id=service.id,
        quantity=2,
        price_at_booking=10000,
    )
    db.session.add(line_item)
    db.session.commit()
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/bookings/api/bookings/update_service_quantity",
        json={
            "booking_id": booking_room.booking_id,
            "room_id": booking_room.room_id,
            "service_id": service.id,
            "change": -1,
        },
    )

    assert response.status_code == 200
    event = AuditEvent.query.one()
    assert event.action == "update_booking_service_quantity"
    assert event.entity_type == "booking_service"
    assert event.entity_id == line_item.id
    assert event.before_data["quantity"] == 2
    assert event.after_data["quantity"] == 1


def test_add_order_records_audit_event(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.status = "checked_in"
    service = Service(hotel_id=hotel.id, name="Nước suối", price=15000)
    db.session.add(service)
    db.session.commit()
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/bookings/api/orders/add",
        json={
            "room_number": booking_room.room.room_number,
            "items": [{"id": service.id, "qty": 2}],
        },
    )

    assert response.status_code == 200
    event = AuditEvent.query.one()
    assert event.action == "add_booking_order"
    assert event.entity_type == "booking_room"
    assert event.entity_id == booking_room.id
    assert event.after_data == {
        "items": [{"service_id": service.id, "quantity": 2, "unit_price": 15000.0}],
    }
