from extensions import db


class BookingServiceBatchAllocation(db.Model):
    __tablename__ = 'booking_service_batch_allocations'

    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False, index=True)
    booking_service_id = db.Column(db.Integer, db.ForeignKey('booking_services.id'), nullable=False, index=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('inventory_batches.id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())

    booking_service = db.relationship('BookingService', back_populates='batch_allocations')
    batch = db.relationship('InventoryBatch', backref='service_allocations')

