from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from decorators import admin_required
from models.audit_event import AuditEvent
from services.tenant_service import tenant_query


audit_bp = Blueprint('audit', __name__)


@audit_bp.route('/')
@login_required
@admin_required
def index():
    return render_template('audit/index.html')


@audit_bp.route('/api/events')
@login_required
@admin_required
def list_events():
    query = tenant_query(AuditEvent)
    action = (request.args.get('action') or '').strip()
    entity_type = (request.args.get('entity_type') or '').strip()
    if action:
        query = query.filter(AuditEvent.action == action)
    if entity_type:
        query = query.filter(AuditEvent.entity_type == entity_type)

    events = query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(100).all()
    return jsonify({
        'total': len(events),
        'items': [{
            'id': event.id,
            'action': event.action,
            'entity_type': event.entity_type,
            'entity_id': event.entity_id,
            'created_at': event.created_at.isoformat() if event.created_at else None,
            'before_data': event.before_data,
            'after_data': event.after_data,
        } for event in events],
    })
