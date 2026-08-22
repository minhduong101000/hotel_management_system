from extensions import db
from services.time_service import utc_now_naive


class BookingServiceBatchAllocation(db.Model):
    __tablename__ = 'booking_service_batch_allocations'
    __table_args__ = (
        db.UniqueConstraint(
            'hotel_id',
            'booking_service_id',
            'batch_id',
            name='uq_booking_service_batch_allocation',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False, index=True)
    booking_service_id = db.Column(db.Integer, db.ForeignKey('booking_services.id'), nullable=False, index=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('inventory_batches.id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive)

    booking_service = db.relationship('BookingService', back_populates='batch_allocations')
    batch = db.relationship('InventoryBatch', backref='service_allocations')
