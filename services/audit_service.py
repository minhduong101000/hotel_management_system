from extensions import db
from models.audit_event import AuditEvent


def record_event(*, hotel_id, actor_user_id, action, entity_type, entity_id,
                 operation_key=None, before_data=None, after_data=None):
    event = AuditEvent(
        hotel_id=hotel_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        operation_key=operation_key,
        before_data=before_data,
        after_data=after_data,
    )
    db.session.add(event)
    return event
