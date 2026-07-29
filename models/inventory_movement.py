from extensions import db


class InventoryMovement(db.Model):
    __tablename__ = 'inventory_movements'

    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False, index=True)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_items.id'), nullable=False, index=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('inventory_batches.id'), nullable=True, index=True)
    expense_id = db.Column(db.Integer, db.ForeignKey('expenses.id'), nullable=True)
    booking_service_id = db.Column(db.Integer, db.ForeignKey('booking_services.id'), nullable=True)
    movement_type = db.Column(db.String(20), nullable=False)
    quantity_delta = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(100), nullable=False)
    note = db.Column(db.String(500), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())

    item = db.relationship('InventoryItem', back_populates='movements')
    batch = db.relationship('InventoryBatch', backref='movements')
    expense = db.relationship('Expense')
    creator = db.relationship('User')

