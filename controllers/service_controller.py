from services.tenant_service import tenant_query, tenant_get_or_404
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from extensions import db
from models.service import Service
from services import audit_service

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
    services = tenant_query(Service).order_by(Service.id.desc()).all() # Mới nhất lên đầu
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
        db.session.flush()
        audit_service.record_event(
            hotel_id=new_service.hotel_id,
            actor_user_id=current_user.id,
            action='create_service',
            entity_type='service',
            entity_id=new_service.id,
            after_data={
                'name': new_service.name,
                'price': float(new_service.price or 0),
            },
        )
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Thêm thành công!'})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})

# 4. API: CẬP NHẬT (SỬA)
@service_bp.route('/api/services/<int:id>', methods=['PUT'])
@login_required
def update_service(id):
    data = request.get_json()
    service = tenant_query(Service).filter_by(id=id).first()
    if service:
        before_data = {'name': service.name, 'price': float(service.price or 0)}
        service.name = data['name']
        service.price = data['price']
        audit_service.record_event(
            hotel_id=service.hotel_id,
            actor_user_id=current_user.id,
            action='update_service',
            entity_type='service',
            entity_id=service.id,
            before_data=before_data,
            after_data={'name': service.name, 'price': float(service.price or 0)},
        )
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Cập nhật thành công!'})
    return jsonify({'success': False, 'msg': 'Không tìm thấy dịch vụ'})

# 5. API: XÓA
@service_bp.route('/api/services/<int:id>', methods=['DELETE'])
@login_required
def delete_service(id):
    service = tenant_query(Service).filter_by(id=id).first()
    if service:
        audit_service.record_event(
            hotel_id=service.hotel_id,
            actor_user_id=current_user.id,
            action='delete_service',
            entity_type='service',
            entity_id=service.id,
            before_data={'name': service.name, 'price': float(service.price or 0)},
        )
        db.session.delete(service)
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Đã xóa dịch vụ!'})
    return jsonify({'success': False, 'msg': 'Không tìm thấy dịch vụ'})
