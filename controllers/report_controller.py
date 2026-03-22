from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from decorators import admin_required
from extensions import db
from models.payment import Payment
from models.booking import Booking
from models.booking_room import BookingRoom
from models.expense import Expense
from datetime import datetime, timedelta
from sqlalchemy import func, and_

report_bp = Blueprint('report', __name__)

# --- VIEW ---
@report_bp.route('/reports/revenue')
@login_required
@admin_required
def revenue():
    return render_template('reports/revenue.html')

# --- API: DOANH THU ---
@report_bp.route('/api/reports/revenue')
@login_required
@admin_required
def get_revenue_data():
    try:
        # Params
        period = request.args.get('period', 'today')  # today, week, month, custom
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        
        now = datetime.now()
        
        if period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0)
            end_date = now
        elif period == 'week':
            start_date = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0)
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

        finalized_time = func.coalesce(BookingRoom.check_out_actual, Booking.updated_at)

        # 1. Doanh thu thực tế (Từ hóa đơn hoàn thành/hủy)
        room_revenue = db.session.query(
            func.coalesce(func.sum(BookingRoom.final_amount), 0)
        ).join(Booking, Booking.id == BookingRoom.booking_id).filter(
            BookingRoom.status.in_(['checked_out', 'cancelled']),
            finalized_time >= start_date,
            finalized_time <= end_date
        ).scalar()

        # 2. Thực thu (Tổng tiền mặt thu vào thực tế trong kỳ - Cash Flow)
        # Bao gồm: Cọc mới, Thanh toán phòng, Dịch vụ, Phí hủy...
        total_cash_in = db.session.query(
            func.coalesce(func.sum(Payment.amount), 0)
        ).filter(
            Payment.amount > 0, # Chỉ tính các khoản thu vào
            Payment.created_at >= start_date,
            Payment.created_at <= end_date
        ).scalar()

        total_cash_out = db.session.query(
            func.coalesce(func.sum(func.abs(Payment.amount)), 0)
        ).filter(
            Payment.amount < 0, # Các khoản chi ra (hoàn tiền)
            Payment.created_at >= start_date,
            Payment.created_at <= end_date
        ).scalar()

        # 3. Số booking hoàn thành
        completed_bookings = Booking.query.filter(
            Booking.status == 'completed',
            Booking.updated_at >= start_date,
            Booking.updated_at <= end_date
        ).count()

        # 5. Tổng chi phí vận hành
        total_expenses = db.session.query(
            func.coalesce(func.sum(Expense.amount), 0)
        ).filter(
            Expense.created_at >= start_date,
            Expense.created_at <= end_date
        ).scalar()

        # 6. Doanh thu và Chi phí theo ngày (cho biểu đồ)
        daily_revenue = db.session.query(
            func.date(finalized_time).label('date'),
            func.sum(BookingRoom.final_amount).label('revenue')
        ).join(Booking, Booking.id == BookingRoom.booking_id).filter(
            BookingRoom.status.in_(['checked_out', 'cancelled']),
            finalized_time >= start_date,
            finalized_time <= end_date
        ).group_by(func.date(finalized_time)).all()

        daily_expenses = db.session.query(
            func.date(Expense.created_at).label('date'),
            func.sum(Expense.amount).label('expense')
        ).filter(
            Expense.created_at >= start_date,
            Expense.created_at <= end_date
        ).group_by(func.date(Expense.created_at)).all()

        # Tổ chức lại dữ liệu biểu đồ
        chart_map = {}
        for r in daily_revenue:
            d_str = r.date.strftime('%d/%m')
            chart_map[d_str] = {'revenue': float(r.revenue or 0), 'expense': 0}
        
        for e in daily_expenses:
            d_str = e.date.strftime('%d/%m')
            if d_str not in chart_map:
                chart_map[d_str] = {'revenue': 0, 'expense': 0}
            chart_map[d_str]['expense'] = float(e.expense or 0)

        chart_data = []
        for d_str in sorted(chart_map.keys()):
            chart_data.append({
                'date': d_str,
                'revenue': chart_map[d_str]['revenue'],
                'expense': chart_map[d_str]['expense']
            })

        # ... (Top rooms extraction remains same)
        top_rooms = db.session.query(
            BookingRoom.room_id,
            func.count(BookingRoom.id).label('count'),
            func.sum(BookingRoom.final_amount).label('total')
        ).join(Booking, Booking.id == BookingRoom.booking_id).filter(
            BookingRoom.status.in_(['checked_out', 'cancelled']),
            finalized_time >= start_date,
            finalized_time <= end_date
        ).group_by(BookingRoom.room_id).order_by(func.sum(BookingRoom.final_amount).desc()).limit(5).all()

        top_rooms_data = []
        for tr in top_rooms:
            from models.room import Room
            room = Room.query.get(tr.room_id)
            top_rooms_data.append({
                'room_number': room.room_number if room else f'#{tr.room_id}',
                'count': tr.count,
                'total': float(tr.total or 0)
            })

        return jsonify({
            'success': True,
            'data': {
                'room_revenue': float(room_revenue or 0),
                'total_net_payment': float(total_cash_in or 0) - float(total_cash_out or 0),
                'total_expenses': float(total_expenses or 0),
                'net_profit': float(room_revenue or 0) - float(total_expenses or 0),
                'completed_bookings': completed_bookings,
                'chart': chart_data,
                'top_rooms': top_rooms_data,
                'period': {
                    'start': start_date.strftime('%d/%m/%Y'),
                    'end': end_date.strftime('%d/%m/%Y')
                }
            }
        })

    except Exception as e:
        print(f"Lỗi báo cáo doanh thu: {e}")
        return jsonify({'success': False, 'msg': str(e)})