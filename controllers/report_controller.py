from flask import Blueprint, render_template
from flask_login import login_required

report_bp = Blueprint('report', __name__)

@report_bp.route('/reports/revenue')
@login_required
def revenue():
    # Số liệu báo cáo
    data = {
        'today_revenue': 5200000,
        'this_month': 150000000,
        'occupancy_rate': 65, # Tỉ lệ lấp đầy %
        'total_guests': 12
    }
    return render_template('reports/index.html', report=data)