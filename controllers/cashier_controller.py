from services.tenant_service import tenant_query, tenant_get_or_404
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from decorators import admin_required
from extensions import db
from models.payment import Payment
from models.booking import Booking
from datetime import datetime, timedelta
from sqlalchemy import desc

cashier_bp = Blueprint('cashier', __name__)

@cashier_bp.route('/reports/cashier')
@login_required
@admin_required
def cashier():
    return render_template('reports/cashier.html')

@cashier_bp.route('/api/reports/cashier')
@login_required
@admin_required
def get_cashier_data():
    try:
        from models.expense import Expense
        period = request.args.get('period', 'today') 
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        
        now = datetime.now()
        
        if period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0)
            end_date = now
        elif period == 'week':
            start_date = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0) # Beginning of week
            end_date = now
        elif period == 'month':
            start_date = now.replace(day=1, hour=0, minute=0, second=0)
            end_date = now
        elif period == 'custom' and start_str and end_str:
            start_date = datetime.strptime(start_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        else:
            start_date = now.replace(hour=0, minute=0, second=0)
            end_date = now

        # 1. Lấy các khoản thu/hoàn tiền từ Payment
        payments_query = tenant_query(Payment).filter(
            Payment.created_at >= start_date,
            Payment.created_at <= end_date
        ).all()

        # 2. Lấy các khoản chi từ Expense
        expenses_query = tenant_query(Expense).filter(
            Expense.created_at >= start_date,
            Expense.created_at <= end_date
        ).all()

        total_received = 0
        total_refunded = 0
        total_expense = 0
        records = []

        # Xử lý Payment
        for p in payments_query:
            amt = float(p.amount)
            if amt >= 0:
                total_received += amt
            else:
                total_refunded += abs(amt)
                
            code = p.booking.code if p.booking else '--'
            customer_name = p.booking.customer.name if p.booking and p.booking.customer else 'Khách'
            
            type_label = ''
            badge_color = 'primary'
            if p.payment_type == 'deposit':
                type_label = 'Nhận cọc'
                badge_color = 'info'
            elif p.payment_type == 'room_payment':
                type_label = 'Thanh toán Phòng'
                badge_color = 'success'
            elif p.payment_type == 'service_payment':
                type_label = 'Thanh toán Dịch vụ'
                badge_color = 'warning'
            elif p.payment_type == 'tax_payment':
                type_label = 'Thuế VAT 8%'
                badge_color = 'primary'
            elif p.payment_type == 'settlement':
                type_label = 'Thanh toán Gộp'
                badge_color = 'success'
            elif p.payment_type == 'cancellation_fee':
                type_label = 'Phí hủy phòng'
                badge_color = 'danger'
            elif p.payment_type == 'refund':
                type_label = 'Hoàn tiền cọc'
                badge_color = 'secondary'
            else:
                type_label = 'Khác'
            
            records.append({
                'id': f"p_{p.id}",
                'time_dt': p.created_at,
                'time': p.created_at.strftime('%H:%M %d/%m/%Y'),
                'booking_id': p.booking_id,
                'booking_code': code,
                'customer_name': customer_name,
                'amount': amt,
                'formatted_amount': "{:,.0f}".format(amt) + ' đ',
                'type_raw': p.payment_type,
                'type_label': type_label,
                'badge_color': badge_color,
                'note': p.note or ''
            })

        # Xử lý Expense (Chỉ tính tổng, không thêm vào records table)
        for e in expenses_query:
            amt = float(e.amount or 0)
            total_expense += amt

        # Sắp xếp lại theo thời gian giảm dần
        records.sort(key=lambda x: x['time_dt'], reverse=True)

        return jsonify({
            'success': True,
            'data': {
                'records': records,
                'total_received': total_received,
                'total_refunded': total_refunded,
                'total_expense': total_expense,
                'net_amount': total_received - total_refunded - total_expense,
                'period_label': f"Từ {start_date.strftime('%d/%m/%Y')} đến {end_date.strftime('%d/%m/%Y')}"
            }
        })
    except Exception as e:
        print(f"Lỗi sổ quỹ: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'msg': str(e)})
