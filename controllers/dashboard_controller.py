from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from models.room import Room
from models.booking import Booking
from repositories.booking_repository import BookingRepository
from repositories.room_repository import RoomRepository
from utils.decorators import admin_required

dashboard_bp = Blueprint('dashboard', __name__)

# --- OPTION 1: VIEW THỐNG KÊ ---
@dashboard_bp.route('/dashboard')
@login_required
def index():
    # Logic thống kê đơn giản
    total = Room.query.count()
    occupied = Room.query.filter_by(status='occupied').count()
    stats = {
        'total': total,
        'available': total - occupied,
        'occupied': occupied,
        'revenue': '5,200,000' # Demo
    }
    return render_template('dashboard/index.html', stats=stats, user_role=current_user.role)

# --- OPTION 2: VIEW TIMELINE ---
@dashboard_bp.route('/dashboard/timeline')
@login_required
def timeline_view():
    return render_template('dashboard/timeline.html', user_role=current_user.role)

# --- API (JSON Data) ---
@dashboard_bp.route('/api/timeline-data')
@login_required
def timeline_data_api():
    try:
        start_str = request.args.get('start', datetime.now().strftime('%Y-%m-%d'))
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        end_date = start_date + timedelta(days=14)

        rooms = RoomRepository.get_all_rooms()
        bookings = BookingRepository.get_bookings_in_range(start_date, end_date)

        return jsonify({
            "status": "success",
            "data": {
                "start_date": start_str,
                "rooms": [{"id": r.id, "number": r.room_number, "type": r.room_type} for r in rooms],
                "bookings": [{
                    "room_id": b.room_id,
                    "customer_name": b.booking.customer.name,
                    "check_in": b.check_in.isoformat(),
                    "check_out": b.check_out.isoformat(),
                    "status": b.booking.status
                } for b in bookings]
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- Demo API Admin Only ---
@dashboard_bp.route('/api/admin/reset-prices', methods=['POST'])
@admin_required
def reset_prices():
    return jsonify({'status': 'success', 'message': 'Admin Action Performed!'})