from extensions import db


class BusinessOperation(db.Model):
    __tablename__ = 'business_operations'

    __table_args__ = (
        db.UniqueConstraint('hotel_id', 'operation_key', name='_hotel_operation_key_uc'),
        db.Index('ix_business_operations_hotel_entity', 'hotel_id', 'entity_type', 'entity_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    operation_key = db.Column(db.String(120), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='processing')
    request_fingerprint = db.Column(db.String(64), nullable=True)
    result_snapshot = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    completed_at = db.Column(db.DateTime, nullable=True)

    payments = db.relationship(
        'Payment',
        back_populates='business_operation',
        lazy=True,
    )
