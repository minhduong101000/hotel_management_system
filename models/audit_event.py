from extensions import db


class AuditEvent(db.Model):
    __tablename__ = 'audit_events'

    __table_args__ = (
        db.Index('ix_audit_events_hotel_created', 'hotel_id', 'created_at'),
        db.Index('ix_audit_events_hotel_entity', 'hotel_id', 'entity_type', 'entity_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    actor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(80), nullable=False)
    entity_type = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    operation_key = db.Column(db.String(120), nullable=True)
    before_data = db.Column(db.JSON, nullable=True)
    after_data = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
