"""API hoàn tiền nhập trực tiếp (chính sách 14-08-2026).

Staff và Admin ngang quyền. Mọi con số do server tính; client chỉ gửi
định danh, cơ sở tính, % hoặc số tiền, phương thức, lý do, client_key.
"""

from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from extensions import db
from models.booking import Booking
from models.payment import Payment
from services import refund_service
from services.tenant_service import tenant_query

refund_bp = Blueprint('refund', __name__)


def _parse_effective_at(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), '%Y-%m-%dT%H:%M')
    except ValueError:
        raise refund_service.RefundError('Thời điểm rời đi không hợp lệ.')


def _find_booking(data):
    booking_id = data.get('booking_id')
    try:
        booking_id = int(booking_id)
    except (TypeError, ValueError):
        return None
    return tenant_query(Booking).filter_by(id=booking_id).first()


@refund_bp.route('/api/refunds/preview', methods=['POST'])
@login_required
def preview_refund():
    data = request.get_json(silent=True) or {}
    booking = _find_booking(data)
    if booking is None:
        return jsonify({'success': False, 'msg': 'Không tìm thấy đơn đặt phòng.'}), 404
    try:
        quote = refund_service.quote_refund(
            booking=booking,
            base=str(data.get('base') or ''),
            percent=data.get('percent'),
            amount=data.get('amount'),
            effective_at=_parse_effective_at(data.get('effective_at')),
        )
    except refund_service.RefundError as error:
        return jsonify({'success': False, 'msg': str(error)}), 400
    return jsonify({
        'success': True,
        'data': {
            'base': quote['base'],
            'percent': quote['percent'],
            'base_value': float(quote['base_value']),
            'refund_amount': float(quote['refund_amount']),
            'cap': float(quote['cap']),
            'already_refunded': float(quote['already_refunded']),
        },
    })


@refund_bp.route('/api/refunds', methods=['POST'])
@login_required
def create_refund():
    data = request.get_json(silent=True) or {}
    booking = _find_booking(data)
    if booking is None:
        return jsonify({'success': False, 'msg': 'Không tìm thấy đơn đặt phòng.'}), 404
    try:
        payment = refund_service.create_refund(
            booking=booking,
            base=str(data.get('base') or ''),
            percent=data.get('percent'),
            amount=data.get('amount'),
            payment_method=data.get('payment_method'),
            reason=data.get('reason'),
            effective_at=_parse_effective_at(data.get('effective_at')),
            actor_user_id=current_user.id,
            client_key=data.get('client_key'),
        )
    except refund_service.RefundCapExceeded as error:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error_code': 'refund_exceeds_cap',
            'msg': str(error),
        }), 400
    except refund_service.RefundError as error:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error_code': 'refund_invalid',
            'msg': str(error),
        }), 400
    db.session.commit()
    return jsonify({
        'success': True,
        'msg': 'Đã ghi nhận hoàn tiền.',
        'data': {
            'payment_id': payment.id,
            'refund_amount': abs(float(payment.amount)),
        },
    })


@refund_bp.route('/api/refunds/<int:payment_id>/reverse', methods=['POST'])
@login_required
def reverse_refund(payment_id):
    data = request.get_json(silent=True) or {}
    payment = tenant_query(Payment).filter_by(id=payment_id).first()
    if payment is None:
        return jsonify({'success': False, 'msg': 'Không tìm thấy dòng hoàn tiền.'}), 404
    try:
        reversal = refund_service.reverse_refund(
            payment=payment,
            reason=data.get('reason'),
            actor_user_id=current_user.id,
            client_key=data.get('client_key'),
        )
    except refund_service.RefundError as error:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error_code': 'refund_reversal_invalid',
            'msg': str(error),
        }), 400
    db.session.commit()
    return jsonify({
        'success': True,
        'msg': 'Đã điều chỉnh dòng hoàn sai.',
        'data': {'payment_id': reversal.id},
    })
