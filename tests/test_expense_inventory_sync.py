from datetime import date

from models.inventory_batch import InventoryBatch
from models.inventory_item import InventoryItem
from models.inventory_movement import InventoryMovement


def test_new_inventory_item_from_expense_is_received_exactly_once(
    client, seed_hotels, login_as
):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/expenses/api/expenses",
        json={
            "category": "Mua sắm",
            "description": "Nhập nước suối",
            "amount": 50_000,
            "expense_date": date.today().isoformat(),
            "sync_inventory": True,
            "warehouse": {
                "code": "WATER-EXPENSE",
                "name": "Nước suối",
                "unit": "chai",
                "quantity": 5,
                "min_quantity": 2,
            },
        },
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    item = InventoryItem.query.filter_by(
        hotel_id=hotel.id,
        code="WATER-EXPENSE",
    ).one()
    batch = InventoryBatch.query.filter_by(inventory_item_id=item.id).one()
    movement = InventoryMovement.query.filter_by(inventory_item_id=item.id).one()
    assert item.quantity == 5
    assert batch.quantity_received == 5
    assert batch.quantity_available == 5
    assert movement.quantity_delta == 5
