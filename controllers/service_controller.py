from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from extensions import db
from models.service import Service

service_bp = Blueprint('service', __name__)

# 1. GIAO DIỆN QUẢN LÝ (HTML)
@service_bp.route('/services')
@login_required
def index():
    return render_template('services/index.html')

# 2. API: LẤY DANH SÁCH (Đã có, dùng lại)
@service_bp.route('/api/services')
@login_required
def get_services():
    services = Service.query.order_by(Service.id.desc()).all() # Mới nhất lên đầu
    return jsonify([s.to_dict() for s in services])

# 3. API: THÊM MỚI
@service_bp.route('/api/services', methods=['POST'])
@login_required
def add_service():
    data = request.get_json()
    try:
        new_service = Service(
            name=data['name'], 
            price=data['price']
        )
        db.session.add(new_service)
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Thêm thành công!'})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})

# 4. API: CẬP NHẬT (SỬA)
@service_bp.route('/api/services/<int:id>', methods=['PUT'])
@login_required
def update_service(id):
    data = request.get_json()
    service = Service.query.get(id)
    if service:
        service.name = data['name']
        service.price = data['price']
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Cập nhật thành công!'})
    return jsonify({'success': False, 'msg': 'Không tìm thấy dịch vụ'})

# 5. API: XÓA
@service_bp.route('/api/services/<int:id>', methods=['DELETE'])
@login_required
def delete_service(id):
    service = Service.query.get(id)
    if service:
        db.session.delete(service)
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Đã xóa dịch vụ!'})
    return jsonify({'success': False, 'msg': 'Không tìm thấy dịch vụ'})