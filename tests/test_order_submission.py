from extensions import db
from datetime import date

from models import BookingService, Service
from models.booking_service_batch_allocation import BookingServiceBatchAllocation
from models.inventory_item import InventoryItem
from models.inventory_movement import InventoryMovement
from services import audit_service, inventory_batch_service, inventory_service


def test_add_order_creates_a_tenant_scoped_line_item(client, seed_hotels, login_as):
    hotel_a, _, user_a, _, booking_room_a, _ = seed_hotels
    booking_room_a.status = "checked_in"
    service = Service(hotel_id=hotel_a.id, name="Nuoc suoi", price=15000)
    db.session.add(service)
    db.session.commit()
    login_as(client, user_a)

    response = client.post(
        f"/{hotel_a.slug}/bookings/api/orders/add",
        json={
            "room_number": "101",
            "booking_room_id": booking_room_a.id,
            "items": [{"id": service.id, "qty": 2}],
        },
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
        json={
            "room_number": "101",
            "booking_room_id": booking_room_a.id,
            "items": [],
        },
    )
    invalid_quantity_response = client.post(
        f"/{hotel_a.slug}/bookings/api/orders/add",
        json={
            "room_number": "101",
            "booking_room_id": booking_room_a.id,
            "items": [{"id": 999, "qty": 0}],
        },
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
        json={
            "room_number": "101",
            "booking_room_id": booking_room_a.id,
            "items": [{"id": foreign_service.id, "qty": 1}],
        },
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
        json={
            "room_number": "101",
            "booking_room_id": booking_room_a.id,
            "items": [{"id": service.id, "qty": 2}],
        },
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
            "booking_room_id": booking_room_a.id,
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
        json={
            "room_number": "101",
            "booking_room_id": booking_room_a.id,
            "items": [{"id": service.id, "qty": 2}],
        },
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
            "booking_room_id": booking_room_a.id,
            "service_id": service.id,
            "change": -1,
        },
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    assert InventoryItem.query.one().quantity == 6
    assert BookingService.query.one().quantity == 1


def test_update_services_preserves_line_and_restores_original_batch(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.status = "checked_in"
    service = Service(hotel_id=hotel.id, name="Nước lô", price=20000)
    item = InventoryItem(
        hotel_id=hotel.id,
        code="NUOC-LO",
        name="Nước lô",
        quantity=0,
        service=service,
    )
    db.session.add_all([service, item])
    db.session.flush()
    batch = inventory_batch_service.create_receipt_batch(
        item=item,
        quantity=5,
        received_at=date(2026, 1, 1),
        expires_at=date(2026, 12, 1),
    )
    line = BookingService(
        hotel_id=hotel.id,
        booking_id=booking_room.booking_id,
        room_id=booking_room.room_id,
        service_id=service.id,
        quantity=3,
        price_at_booking=service.price,
    )
    db.session.add(line)
    db.session.flush()
    inventory_service.deduct_inventory(
        hotel.id,
        service.id,
        3,
        booking_service=line,
    )
    db.session.commit()
    line_id = line.id
    login_as(client, user)

    reduce_response = client.post(
        f"/{hotel.slug}/bookings/api/bookings/update_services",
        json={
            "number": booking_room.room.room_number,
            "booking_room_id": booking_room.id,
            "services": [{"service_id": service.id, "quantity": 1}],
        },
    )

    assert reduce_response.status_code == 200
    line = db.session.get(BookingService, line_id)
    allocation = BookingServiceBatchAllocation.query.one()
    assert line.quantity == 1
    assert allocation.booking_service_id == line_id
    assert allocation.quantity == 1
    assert batch.quantity_available == 4
    assert item.quantity == 4

    remove_response = client.post(
        f"/{hotel.slug}/bookings/api/bookings/update_services",
        json={
            "number": booking_room.room.room_number,
            "booking_room_id": booking_room.id,
            "services": [],
        },
    )

    assert remove_response.status_code == 200
    line = db.session.get(BookingService, line_id)
    assert line is not None
    assert line.quantity == 0
    assert BookingServiceBatchAllocation.query.one().quantity == 0
    assert batch.quantity_available == 5
    assert item.quantity == 5
    assert [
        movement.quantity_delta
        for movement in InventoryMovement.query.filter_by(
            booking_service_id=line_id
        ).order_by(InventoryMovement.id).all()
    ] == [-3, 2, 1]


def test_finalized_room_rejects_all_service_mutations(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.status = "checked_out"
    service = Service(hotel_id=hotel.id, name="Đã chốt", price=20000)
    line = BookingService(
        hotel_id=hotel.id,
        booking_id=booking_room.booking_id,
        room_id=booking_room.room_id,
        service=service,
        quantity=1,
        price_at_booking=service.price,
    )
    db.session.add_all([service, line])
    db.session.commit()
    login_as(client, user)

    responses = [
        client.post(
            f"/{hotel.slug}/bookings/api/bookings/update_service_quantity",
            json={
                "booking_room_id": booking_room.id,
                "service_id": service.id,
                "change": 1,
            },
        ),
        client.post(
            f"/{hotel.slug}/bookings/api/bookings/update_services",
            json={
                "number": booking_room.room.room_number,
                "booking_room_id": booking_room.id,
                "services": [],
            },
        ),
        client.post(
            f"/{hotel.slug}/bookings/api/orders/add",
            json={
                "room_number": booking_room.room.room_number,
                "booking_room_id": booking_room.id,
                "items": [{"id": service.id, "qty": 1}],
            },
        ),
    ]

    assert [response.status_code for response in responses] == [409, 409, 409]
    assert all(
        response.json["error_code"] == "service_bill_finalized"
        for response in responses
    )
    assert BookingService.query.one().quantity == 1


def test_service_mutation_requires_booking_room_identity(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.status = "checked_in"
    service = Service(hotel_id=hotel.id, name="Yêu cầu phòng", price=10000)
    db.session.add(service)
    db.session.commit()
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/bookings/api/orders/add",
        json={
            "room_number": booking_room.room.room_number,
            "items": [{"id": service.id, "qty": 1}],
        },
    )

    assert response.status_code == 400
    assert response.json["error_code"] == "booking_room_required"
    assert BookingService.query.count() == 0


def test_order_failure_rolls_back_batch_allocation_and_movement(
    client,
    seed_hotels,
    login_as,
    monkeypatch,
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.status = "checked_in"
    service = Service(hotel_id=hotel.id, name="Rollback", price=10000)
    item = InventoryItem(
        hotel_id=hotel.id,
        code="ROLLBACK",
        name="Rollback",
        quantity=0,
        service=service,
    )
    db.session.add_all([service, item])
    db.session.flush()
    batch = inventory_batch_service.create_receipt_batch(
        item=item,
        quantity=2,
        received_at=date(2026, 1, 1),
        expires_at=date(2026, 12, 1),
    )
    db.session.commit()
    receipt_movement_count = InventoryMovement.query.count()
    login_as(client, user)

    def fail_audit(**_kwargs):
        raise RuntimeError("forced audit failure")

    monkeypatch.setattr(audit_service, "record_event", fail_audit)
    response = client.post(
        f"/{hotel.slug}/bookings/api/orders/add",
        json={
            "room_number": booking_room.room.room_number,
            "booking_room_id": booking_room.id,
            "items": [{"id": service.id, "qty": 1}],
        },
    )

    assert response.status_code == 500
    db.session.expire_all()
    assert item.quantity == 2
    assert batch.quantity_available == 2
    assert BookingService.query.count() == 0
    assert BookingServiceBatchAllocation.query.count() == 0
    assert InventoryMovement.query.count() == receipt_movement_count


def test_service_frontend_submits_booking_room_identity():
    service_source = open("static/js/service.js", encoding="utf-8").read()
    checkout_source = open("static/js/checkout.js", encoding="utf-8").read()
    timeline_source = open(
        "static/js/timeline_manager.js",
        encoding="utf-8",
    ).read()

    assert "currentOrderBookingRoomId" in service_source
    assert "booking_room_id: currentOrderBookingRoomId" in service_source
    assert "booking_room_id: currentBookingRoomId" in checkout_source
    assert "booking_room_id:" in timeline_source
