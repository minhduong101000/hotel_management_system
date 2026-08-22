from extensions import db
from services.time_service import utc_now_naive


class InventoryBatch(db.Model):
    __tablename__ = 'inventory_batches'

    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False, index=True)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_items.id'), nullable=False, index=True)
    expense_id = db.Column(db.Integer, db.ForeignKey('expenses.id'), nullable=True)
    batch_code = db.Column(db.String(64), nullable=False)
    received_at = db.Column(db.Date, nullable=False)
    expires_at = db.Column(db.Date, nullable=True)
    quantity_received = db.Column(db.Integer, nullable=False)
    quantity_available = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default='active')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive)

    __table_args__ = (
        db.UniqueConstraint('hotel_id', 'batch_code', name='_hotel_inventory_batch_code_uc'),
    )

    item = db.relationship('InventoryItem', back_populates='batches')
    expense = db.relationship('Expense')
    creator = db.relationship('User')

