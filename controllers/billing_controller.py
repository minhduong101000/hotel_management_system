from services.tenant_service import tenant_query, tenant_get_or_404
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from extensions import db
from models.booking import Booking
from models.booking_room import BookingRoom
from models.booking_service import BookingService
from models.payment import Payment
from sqlalchemy import desc
import re

from services import payment_service
from services import time_service

billing_bp = Blueprint('billing', __name__)


def _effective_refunds_data(booking):
    """Cac dong hoan con hieu luc cho hoa don khach (cap sai/dao da triet tieu)."""
    return [
        {
            'amount': abs(float(p.amount or 0)),
            'method': p.payment_method,
            'time': time_service.format_business(p.created_at, '%d/%m/%Y %H:%M'),
            'note': p.note or '',
        }
        for p in payment_service.effective_payments(booking)
        if p.payment_type == 'refund'
    ]

@billing_bp.route('/billing')
@login_required
def index():
    # Render trang giao diện chính
    return render_template('billing/index.html')

@billing_bp.route('/api/billing/list')
@login_required
def get_billing_list():
    try:
        start_str = request.args.get('start', '')
        end_str = request.args.get('end', '')
        from sqlalchemy import func
        finalized_time = func.coalesce(BookingRoom.check_out_actual, Booking.updated_at)
        query = tenant_query(BookingRoom).join(Booking, Booking.id == BookingRoom.booking_id).filter(
            BookingRoom.status.in_(['checked_out', 'cancelled'])
        )
        
        from datetime import datetime
        from services import time_service
        # Loc theo NGAY nghiep vu (gio VN) doi sang cua so UTC — dong nhat voi
        # bao cao/so quy sau chuan hoa thoi gian 14-08.
        if start_str and end_str:
            start_utc, end_utc = time_service.business_period_to_utc(
                datetime.strptime(start_str, '%Y-%m-%d').date(),
                datetime.strptime(end_str, '%Y-%m-%d').date(),
            )
            query = query.filter(finalized_time >= start_utc, finalized_time < end_utc)
        elif start_str:
            start_utc, _ = time_service.business_period_to_utc(
                datetime.strptime(start_str, '%Y-%m-%d').date(),
                datetime.strptime(start_str, '%Y-%m-%d').date(),
            )
            query = query.filter(finalized_time >= start_utc)
            
        finalized_rooms = query.order_by(desc(finalized_time)).all()
        
        data = []
        for br in finalized_rooms:
            booking = br.booking
            if not booking:
                continue

            checkout_time = br.check_out_actual or booking.updated_at or booking.created_at
            data.append({
                'id': br.id,
                'booking_id': booking.id,
                'code': booking.code,
                'room_number': br.room.room_number if br.room else 'N/A',
                'customer_name': booking.customer.name if booking.customer else 'Khách vãng lai',
                'total_amount': float(br.final_amount or 0),
                'prepaid_amount': 0,
                'date': time_service.format_business(checkout_time, '%d/%m/%Y %H:%M'),
                'status': br.status
            })
            
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})

@billing_bp.route('/api/billing/detail/<int:entry_id>')
@login_required
def get_billing_detail(entry_id):
    try:
        detail_type = request.args.get('type', 'booking')

        if detail_type == 'room':
            br = tenant_get_or_404(BookingRoom, entry_id)
            booking = br.booking

            if not booking:
                return jsonify({'success': False, 'msg': 'Không tìm thấy đơn gốc của phòng này.'})

            services = tenant_query(BookingService).filter_by(
                booking_id=booking.id,
                room_id=br.room_id
            ).all()

            services_data = []
            service_total = 0.0
            for bs in services:
                line_total = float((bs.quantity or 0) * float(bs.price_at_booking or 0))
                service_total += line_total
                services_data.append({
                    'name': bs.service.name if bs.service else 'Dịch vụ đã xóa',
                    'quantity': bs.quantity,
                    'price': float(bs.price_at_booking or 0),
                    'total': line_total
                })

            room_number = br.room.room_number if br.room else 'N/A'

            tax_payment_q = tenant_query(Payment).filter(
                Payment.booking_id == booking.id,
                Payment.payment_type == 'tax_payment',
                Payment.note.like(f"%phòng {room_number}%")
            )
            tax_amount = sum(float(p.amount or 0) for p in tax_payment_q.all())

            total_amount = float(br.final_amount or 0)
            room_only_amount = total_amount - service_total - tax_amount
            if room_only_amount < 0:
                room_only_amount = 0

            room_payment_q = tenant_query(Payment).filter(
                Payment.booking_id == booking.id,
                Payment.note.like(f"%phòng {room_number}%")
            )
            cash_received = sum(float(p.amount or 0) for p in room_payment_q.all())

            checkout_time = br.check_out_actual or booking.updated_at or booking.created_at
            rooms_data = [{
                'room_number': room_number,
                'check_in': time_service.format_business(br.check_in_actual, '%d/%m/%Y %H:%M') if br.check_in_actual else (
                    br.check_in_expected.strftime('%d/%m/%Y %H:%M') if br.check_in_expected else 'N/A'
                ),
                'check_out': time_service.format_business(checkout_time, '%d/%m/%Y %H:%M') if checkout_time else 'N/A',
                'rental_type': 'Theo giờ' if br.rental_type == 'hourly' else 'Theo ngày',
                'price_snapshot': room_only_amount,
                'amount': total_amount
            }]

            cancellation_detail = {
                'is_cancelled': False,
                'reason': '',
                'refund_percent': 0,
                'fee_percent': 0,
                'refund_amount': 0,
                'original_deposit': float(booking.prepaid_amount or 0)
            }

            if br.status == 'cancelled':
                # Ưu tiên dữ liệu đã lưu trực tiếp theo từng phòng (source of truth mới).
                if float(br.room_deposit_original or 0) > 0 or float(br.cancellation_refund_amount or 0) > 0:
                    cancellation_detail = {
                        'is_cancelled': True,
                        'reason': 'Đã hủy phòng',
                        'refund_percent': float(br.cancellation_refund_percent or 0),
                        'fee_percent': float(br.cancellation_fee_percent or 0),
                        'refund_amount': float(br.cancellation_refund_amount or 0),
                        'original_deposit': float(br.room_deposit_original or 0)
                    }

                    return jsonify({
                        'success': True,
                        'data': {
                            'booking_id': booking.id,
                            'booking_id': booking.id,
                    'code': f"{booking.code}-R{room_number}",
                            'customer': booking.customer.name if booking.customer else 'Khách vãng lai',
                            'rooms': rooms_data,
                            'services': services_data,
                            'tax_amount': tax_amount,
                            'tax_rate': 8 if tax_amount > 0 else 0,
                            'total_amount': total_amount,
                            'prepaid_amount': float(cancellation_detail.get('original_deposit', 0) or 0),
                            'final_payment': -float(cancellation_detail.get('refund_amount', 0) or 0),
                            'note': booking.note or '',
                            'refunds': _effective_refunds_data(booking),
                            'cancellation_detail': cancellation_detail
                        }
                    })

                note_text = booking.note or ''
                cancel_note = ''
                cancel_matches = re.findall(r'\[HỦY:\s*(.*?)\]', note_text, flags=re.IGNORECASE)
                if cancel_matches:
                    # Ưu tiên lấy log hủy có chứa đúng số phòng này.
                    for one_note in reversed(cancel_matches):
                        if room_number and room_number in one_note:
                            cancel_note = one_note
                            break
                    if not cancel_note:
                        cancel_note = cancel_matches[-1]
                elif 'HỦY' in note_text.upper():
                    cancel_note = note_text[-240:]

                refund_amount = 0.0
                refund_percent = 0.0
                fee_percent = 0.0
                original_deposit = float(booking.prepaid_amount or 0)

                alloc_match = re.search(r'Cọc phân bổ:\s*([0-9\.,]+)\s*đ', cancel_note, flags=re.IGNORECASE)
                if alloc_match:
                    alloc_str = alloc_match.group(1).replace('.', '').replace(',', '.')
                    try:
                        original_deposit = float(alloc_str)
                    except ValueError:
                        original_deposit = float(booking.prepaid_amount or 0)

                amt_match = re.search(r'Hoàn tiền:\s*([0-9\.,]+)\s*đ', cancel_note, flags=re.IGNORECASE)
                if amt_match:
                    amount_str = amt_match.group(1).replace('.', '').replace(',', '.')
                    try:
                        refund_amount = float(amount_str)
                    except ValueError:
                        refund_amount = 0.0

                # Hỗ trợ cả 2 format:
                # 1) "(Hoàn 50% cọc)"
                # 2) "(50%)"
                refund_pct_match = re.search(r'Hoàn\s*(\d+(?:[\.,]\d+)?)\s*%', cancel_note, flags=re.IGNORECASE)
                if not refund_pct_match:
                    refund_pct_match = re.search(r'\((\d+(?:[\.,]\d+)?)%\)', cancel_note)
                if refund_pct_match:
                    refund_percent = float(refund_pct_match.group(1).replace(',', '.'))
                elif original_deposit > 0 and refund_amount > 0:
                    # Fallback: nếu không parse được % nhưng có số tiền hoàn, suy ra từ tiền cọc gốc.
                    refund_percent = (refund_amount / original_deposit) * 100.0

                fee_pct_match = re.search(r'Phí hủy:\s*(\d+(?:[\.,]\d+)?)\s*%', cancel_note, flags=re.IGNORECASE)
                if fee_pct_match:
                    fee_percent = float(fee_pct_match.group(1).replace(',', '.'))
                else:
                    fee_percent = max(0.0, 100.0 - refund_percent)

                # Chuẩn hóa tỷ lệ vào biên 0..100 để tránh hiển thị sai do dữ liệu cũ.
                refund_percent = max(0.0, min(100.0, refund_percent))
                fee_percent = max(0.0, min(100.0, fee_percent))

                reason = cancel_note.split('Hoàn tiền:')[0].strip(' .-') if cancel_note else 'Đã hủy phòng'

                cancellation_detail = {
                    'is_cancelled': True,
                    'reason': reason,
                    'refund_percent': refund_percent,
                    'fee_percent': fee_percent,
                    'refund_amount': refund_amount,
                    'original_deposit': original_deposit
                }

            return jsonify({
                'success': True,
                'data': {
                    'code': f"{booking.code}-R{room_number}",
                    'customer': booking.customer.name if booking.customer else 'Khách vãng lai',
                    'rooms': rooms_data,
                    'services': services_data,
                    'tax_amount': tax_amount,
                    'tax_rate': 8 if tax_amount > 0 else 0,
                    'total_amount': total_amount,
                    'prepaid_amount': float(cancellation_detail.get('original_deposit', 0) or 0) if br.status == 'cancelled' else max(total_amount - cash_received, 0),
                    'final_payment': -float(cancellation_detail.get('refund_amount', 0) or 0) if br.status == 'cancelled' else cash_received,
                    'note': booking.note or '',
                    'refunds': _effective_refunds_data(booking),
                    'cancellation_detail': cancellation_detail
                }
            })

        booking = tenant_get_or_404(Booking, entry_id)
        
        # 1. Chi tiết phòng
        rooms_data = []
        for br in booking.rooms:
            room_services = tenant_query(BookingService).filter_by(booking_id=booking.id, room_id=br.room_id).all()
            service_total = sum(float((x.quantity or 0) * float(x.price_at_booking or 0)) for x in room_services)
            room_only_amount = float(br.final_amount or 0) - service_total
            if room_only_amount < 0:
                room_only_amount = 0

            rooms_data.append({
                'room_number': br.room.room_number if br.room else 'N/A',
                'check_in': time_service.format_business(br.check_in_actual, '%d/%m/%Y %H:%M') if br.check_in_actual else 'N/A',
                'check_out': time_service.format_business(br.check_out_actual, '%d/%m/%Y %H:%M') if br.check_out_actual else 'N/A',
                'rental_type': 'Theo giờ' if br.rental_type == 'hourly' else 'Theo ngày',
                'price_snapshot': room_only_amount,
                'amount': float(br.final_amount or 0)
            })
            
        # 2. Chi tiết dịch vụ
        services_data = []
        for bs in booking.services:
            services_data.append({
                'name': bs.service.name if bs.service else 'Dịch vụ đã xóa',
                'quantity': bs.quantity,
                'price': float(bs.price_at_booking or 0),
                'total': float(bs.quantity * (bs.price_at_booking or 0))
            })
            
        total_rooms = sum(r['amount'] for r in rooms_data)
        total_services = sum(s['total'] for s in services_data)
        calculated_total = total_rooms + total_services
        cash_received = sum(float(p.amount or 0) for p in booking.payments)
        tax_amount = sum(float(p.amount or 0) for p in booking.payments if p.payment_type == 'tax_payment')

        refunds_data = _effective_refunds_data(booking)

        return jsonify({
            'success': True,
            'data': {
                'booking_id': booking.id,
                'code': booking.code,
                'customer': booking.customer.name if booking.customer else 'Khách vãng lai',
                'rooms': rooms_data,
                'services': services_data,
                'tax_amount': tax_amount,
                'tax_rate': 8 if tax_amount > 0 else 0,
                'total_amount': calculated_total, # Dùng giá trị tính toán thay vì booking.total_amount (để sửa lỗi HĐ cũ)
                'prepaid_amount': max(calculated_total - cash_received, 0),
                'final_payment': cash_received,
                'refunds': refunds_data,
                'note': booking.note or ''
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})