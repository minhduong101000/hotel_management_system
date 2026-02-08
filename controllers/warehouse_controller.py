from flask import Blueprint, render_template
from flask_login import login_required

warehouse_bp = Blueprint('warehouse', __name__)

@warehouse_bp.route('/warehouse')
@login_required
def index():
    inventory = [
        {'code': 'KH01', 'name': 'Khăn tắm lớn', 'quantity': 150, 'status': 'ok'},
        {'code': 'KH02', 'name': 'Khăn mặt',     'quantity': 200, 'status': 'ok'},
        {'code': 'GA01', 'name': 'Ga giường đôi','quantity': 50,  'status': 'low'}, # Sắp hết
        {'code': 'BC01', 'name': 'Bàn chải',     'quantity': 500, 'status': 'ok'},
        {'code': 'DR01', 'name': 'Dầu gội gói',  'quantity': 20,  'status': 'critical'}, # Báo động đỏ
    ]
    return render_template('warehouse/index.html', inventory=inventory)