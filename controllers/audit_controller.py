from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required
from datetime import datetime, timedelta

from decorators import admin_required
from models.audit_event import AuditEvent
from models.user import User
from services.tenant_service import tenant_query


audit_bp = Blueprint('audit', __name__)


AUDIT_GROUP_ACTIONS = {
    'room': {'checkin', 'checkout', 'clean_room'},
    'booking': {'create_booking', 'create_group_booking', 'update_booking_timeline', 'reschedule_booking_keep_price', 'reschedule_booking_reprice', 'cancel_booking', 'group_checkout'},
    'service': {'add_booking_order', 'update_booking_service_quantity', 'update_group_booking_services', 'create_service', 'update_service', 'delete_service'},
    'inventory': {'create_inventory', 'update_inventory', 'delete_inventory', 'restock_inventory'},
    'price': {'update_base_price', 'create_price_rule', 'update_price_rule', 'delete_price_rule'},
    'expense': {'create_expense', 'delete_expense'},
    'staff': {'create_staff_user', 'reset_staff_password', 'delete_staff_user'},
}


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
    group = (request.args.get('group') or '').strip()
    start = (request.args.get('start') or '').strip()
    end = (request.args.get('end') or '').strip()
    if action:
        query = query.filter(AuditEvent.action == action)
    if entity_type:
        query = query.filter(AuditEvent.entity_type == entity_type)
    if group and group in AUDIT_GROUP_ACTIONS:
        query = query.filter(AuditEvent.action.in_(AUDIT_GROUP_ACTIONS[group]))
    if start:
        query = query.filter(AuditEvent.created_at >= datetime.strptime(start, '%Y-%m-%d'))
    if end:
        query = query.filter(AuditEvent.created_at < datetime.strptime(end, '%Y-%m-%d') + timedelta(days=1))

    try:
        page = max(1, int(request.args.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = min(100, max(1, int(request.args.get('per_page', 25))))
    except (TypeError, ValueError):
        per_page = 25

    total = query.count()
    events = query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    actor_names = {
        user.id: user.username
        for user in User.query.filter(User.id.in_([event.actor_user_id for event in events if event.actor_user_id])).all()
    }
    return jsonify({
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': max(1, (total + per_page - 1) // per_page),
        'items': [{
            'id': event.id,
            'action': event.action,
            'entity_type': event.entity_type,
            'entity_id': event.entity_id,
            'actor_name': actor_names.get(event.actor_user_id, 'Hệ thống'),
            'created_at': event.created_at.isoformat() if event.created_at else None,
            'before_data': event.before_data,
            'after_data': event.after_data,
        } for event in events],
    })
