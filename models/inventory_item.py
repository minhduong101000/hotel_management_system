from extensions import db

class InventoryItem(db.Model):
    __tablename__ = 'inventory_items'

    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    
    __table_args__ = (
        db.UniqueConstraint('hotel_id', 'code', name='_hotel_inv_code_uc'),
    )
    unit = db.Column(db.String(20), default='cái')  # cái, chai, gói, kg...
    quantity = db.Column(db.Integer, default=0)
    min_quantity = db.Column(db.Integer, default=10)  # Ngưỡng cảnh báo hết hàng
    price = db.Column(db.Numeric(15, 2), default=0)  # Giá nhập
    
    # Liên kết với dịch vụ (optional) — khi khách dùng dịch vụ sẽ tự trừ kho
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=True)
    service = db.relationship('Service', backref='inventory_items')
    batches = db.relationship('InventoryBatch', back_populates='item')
    movements = db.relationship('InventoryMovement', back_populates='item')

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'unit': self.unit,
            'quantity': self.quantity,
            'min_quantity': self.min_quantity,
            'price': float(self.price or 0),
            'service_id': self.service_id,
            'service_name': self.service.name if self.service else None,
            'status': 'critical' if self.quantity <= 0 else ('low' if self.quantity <= self.min_quantity else 'ok')
        }
