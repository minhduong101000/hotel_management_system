from datetime import date

from extensions import db
from models.expense import Expense
from models.inventory_item import InventoryItem


def test_synced_expense_cannot_be_deleted_directly(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    item = InventoryItem(hotel_id=hotel.id, code='SYNCED', name='Hàng đã nhập', quantity=1)
    expense = Expense(hotel_id=hotel.id, category='Mua sắm', description='Nhập kho [KHO:SYNCED]', amount=10000, expense_date=date.today(), created_by=admin.id)
    db.session.add_all([item, expense])
    db.session.commit()
    login_as(client, admin)

    response = client.delete(f'/{hotel.slug}/expenses/api/expenses/{expense.id}')

    assert response.status_code == 409
    assert Expense.query.get(expense.id) is not None


def test_unsynced_expense_keeps_existing_delete_behavior(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    expense = Expense(hotel_id=hotel.id, category='Khác', description='Chi phí văn phòng', amount=10000, expense_date=date.today(), created_by=admin.id)
    db.session.add(expense)
    db.session.commit()
    login_as(client, admin)

    response = client.delete(f'/{hotel.slug}/expenses/api/expenses/{expense.id}')

    assert response.status_code == 200
    assert Expense.query.get(expense.id) is None
