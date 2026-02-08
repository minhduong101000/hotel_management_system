from flask import Blueprint, render_template
from flask_login import login_required, current_user
from datetime import datetime

staff_bp = Blueprint('staff', __name__)

@staff_bp.route('/staff/shifts')
@login_required
def shifts():
    # Thông tin ca trực giả lập
    current_shift = {
        'name': 'Ca Sáng (6:00 - 14:00)',
        'staff_name': current_user.username if current_user.is_authenticated else 'Admin',
        'cash_start': 2000000, # Tiền đầu ca
        'cash_in': 5500000,    # Tiền thu vào
        'cash_out': 500000,    # Tiền chi ra
        'total_now': 7000000   # Tổng hiện tại
    }
    return render_template('staff/shifts.html', shift=current_shift, now=datetime.now())