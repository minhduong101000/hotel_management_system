from extensions import db
from models import BookingService, Service
from models.inventory_item import InventoryItem


def test_add_order_creates_a_tenant_scoped_line_item(client, seed_hotels, login_as):
    hotel_a, _, user_a, _, booking_room_a, _ = seed_hotels
    booking_room_a.status = "checked_in"
    service = Service(hotel_id=hotel_a.id, name="Nuoc suoi", price=15000)
    db.session.add(service)
    db.session.commit()
    login_as(client, user_a)

    response = client.post(
        f"/{hotel_a.slug}/bookings/api/orders/add",
        json={"room_number": "101", "items": [{"id": service.id, "qty": 2}]},
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    line_item = BookingService.query.one()
    assert line_item.hotel_id == hotel_a.id
    assert line_item.quantity == 2


def test_add_order_rejects_empty_or_non_positive_items(client, seed_hotels, login_as):
    hotel_a, _, user_a, _, booking_room_a, _ = seed_hotels
    booking_room_a.status = "checked_in"
    db.session.commit()
    login_as(client, user_a)

    empty_response = client.post(
        f"/{hotel_a.slug}/bookings/api/orders/add",
        json={"room_number": "101", "items": []},
    )
    invalid_quantity_response = client.post(
        f"/{hotel_a.slug}/bookings/api/orders/add",
        json={"room_number": "101", "items": [{"id": 999, "qty": 0}]},
    )

    assert empty_response.status_code == 400
    assert empty_response.json["success"] is False
    assert invalid_quantity_response.status_code == 400
    assert invalid_quantity_response.json["success"] is False
    assert BookingService.query.count() == 0


def test_add_order_rejects_service_from_another_hotel(client, seed_hotels, login_as):
    hotel_a, hotel_b, user_a, _, booking_room_a, _ = seed_hotels
    booking_room_a.status = "checked_in"
    foreign_service = Service(hotel_id=hotel_b.id, name="Foreign service", price=99000)
    db.session.add(foreign_service)
    db.session.commit()
    login_as(client, user_a)

    response = client.post(
        f"/{hotel_a.slug}/bookings/api/orders/add",
        json={"room_number": "101", "items": [{"id": foreign_service.id, "qty": 1}]},
    )

    assert response.status_code == 404
    assert response.json["success"] is False
    assert BookingService.query.count() == 0


def test_add_order_rejects_insufficient_inventory_without_partial_mutation(
    client, seed_hotels, login_as
):
    hotel_a, _, user_a, _, booking_room_a, _ = seed_hotels
    booking_room_a.status = "checked_in"
    service = Service(hotel_id=hotel_a.id, name="Minibar", price=30000)
    db.session.add(service)
    db.session.flush()
    inventory = InventoryItem(
        hotel_id=hotel_a.id,
        code="MINIBAR",
        name="Minibar",
        quantity=1,
        service_id=service.id,
    )
    db.session.add(inventory)
    db.session.commit()
    login_as(client, user_a)

    response = client.post(
        f"/{hotel_a.slug}/bookings/api/orders/add",
        json={"room_number": "101", "items": [{"id": service.id, "qty": 2}]},
    )

    assert response.status_code == 409
    assert response.json["success"] is False
    assert InventoryItem.query.one().quantity == 1
    assert BookingService.query.count() == 0


def test_update_services_adjusts_inventory_by_the_quantity_difference(
    client, seed_hotels, login_as
):
    hotel_a, _, user_a, _, booking_room_a, _ = seed_hotels
    booking_room_a.status = "checked_in"
    service = Service(hotel_id=hotel_a.id, name="Nuoc ngot", price=20000)
    db.session.add(service)
    db.session.flush()
    inventory = InventoryItem(
        hotel_id=hotel_a.id,
        code="NUOCNGOT",
        name="Nuoc ngot",
        quantity=7,
        service_id=service.id,
    )
    db.session.add_all([
        inventory,
        BookingService(
            hotel_id=hotel_a.id,
            booking_id=booking_room_a.booking_id,
            room_id=booking_room_a.room_id,
            service_id=service.id,
            quantity=1,
            price_at_booking=service.price,
        ),
    ])
    db.session.commit()
    login_as(client, user_a)

    response = client.post(
        f"/{hotel_a.slug}/bookings/api/bookings/update_services",
        json={
            "number": "101",
            "services": [{"service_id": service.id, "quantity": 3}],
        },
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    assert InventoryItem.query.one().quantity == 5
    assert BookingService.query.one().quantity == 3


def test_add_order_only_mutates_inventory_of_current_hotel(client, seed_hotels, login_as):
    hotel_a, hotel_b, user_a, _, booking_room_a, _ = seed_hotels
    booking_room_a.status = "checked_in"
    service = Service(hotel_id=hotel_a.id, name="Tra", price=10000)
    db.session.add(service)
    db.session.flush()
    own_inventory = InventoryItem(
        hotel_id=hotel_a.id,
        code="TRA-A",
        name="Tra A",
        quantity=5,
        service_id=service.id,
    )
    foreign_inventory = InventoryItem(
        hotel_id=hotel_b.id,
        code="TRA-B",
        name="Tra B",
        quantity=5,
        service_id=service.id,
    )
    db.session.add_all([own_inventory, foreign_inventory])
    db.session.commit()
    login_as(client, user_a)

    response = client.post(
        f"/{hotel_a.slug}/bookings/api/orders/add",
        json={"room_number": "101", "items": [{"id": service.id, "qty": 2}]},
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    assert InventoryItem.query.filter_by(hotel_id=hotel_a.id).one().quantity == 3
    assert InventoryItem.query.filter_by(hotel_id=hotel_b.id).one().quantity == 5


def test_update_service_quantity_restores_inventory_when_item_is_removed(
    client, seed_hotels, login_as
):
    hotel_a, _, user_a, _, booking_room_a, _ = seed_hotels
    booking_room_a.status = "checked_in"
    service = Service(hotel_id=hotel_a.id, name="Bia", price=25000)
    db.session.add(service)
    db.session.flush()
    db.session.add_all([
        InventoryItem(
            hotel_id=hotel_a.id,
            code="BIA",
            name="Bia",
            quantity=5,
            service_id=service.id,
        ),
        BookingService(
            hotel_id=hotel_a.id,
            booking_id=booking_room_a.booking_id,
            room_id=booking_room_a.room_id,
            service_id=service.id,
            quantity=2,
            price_at_booking=service.price,
        ),
    ])
    db.session.commit()
    login_as(client, user_a)

    response = client.post(
        f"/{hotel_a.slug}/bookings/api/bookings/update_service_quantity",
        json={
            "booking_id": booking_room_a.booking_id,
            "service_id": service.id,
            "change": -1,
        },
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    assert InventoryItem.query.one().quantity == 6
    assert BookingService.query.one().quantity == 1
