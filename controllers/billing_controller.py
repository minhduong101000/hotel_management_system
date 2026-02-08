from flask import Blueprint, render_template
from flask_login import login_required

billing_bp = Blueprint('billing', __name__)

@billing_bp.route('/billing')
@login_required
def index():
    # Danh sách khách đang chờ thanh toán
    bills = [
        {'id': 101, 'room': '101', 'customer': 'Nguyễn Văn A', 'check_in': '19/01 12:00', 'check_out': '20/01 12:00', 'total': 350000, 'status': 'pending'},
        {'id': 102, 'room': '205', 'customer': 'Lê Văn C',    'check_in': '19/01 14:00', 'check_out': '19/01 18:00', 'total': 120000, 'status': 'pending'},
    ]
    return render_template('billing/index.html', bills=bills)