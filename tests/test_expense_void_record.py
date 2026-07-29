from datetime import date

from extensions import db
from models.expense import Expense
from models.inventory_item import InventoryItem


def test_admin_can_void_synced_expense_without_changing_inventory(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    item = InventoryItem(hotel_id=hotel.id, code='VOIDED', name='Hàng', quantity=4)
    expense = Expense(hotel_id=hotel.id, category='Mua sắm', description='Nhập kho [KHO:VOIDED]', amount=10000, expense_date=date.today(), created_by=admin.id)
    db.session.add_all([item, expense])
    db.session.commit()
    login_as(client, admin)

    response = client.post(f'/{hotel.slug}/expenses/api/expenses/{expense.id}/void', json={'reason': 'Nhập nhầm hóa đơn'})

    assert response.status_code == 200
    assert expense.is_voided is True
    assert expense.void_reason == 'Nhập nhầm hóa đơn'
    assert item.quantity == 4


def test_voiding_expense_requires_reason(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    expense = Expense(hotel_id=hotel.id, category='Khác', description='Chi phí', amount=10000, expense_date=date.today(), created_by=admin.id)
    db.session.add(expense)
    db.session.commit()
    login_as(client, admin)

    response = client.post(f'/{hotel.slug}/expenses/api/expenses/{expense.id}/void', json={'reason': ''})

    assert response.status_code == 400
