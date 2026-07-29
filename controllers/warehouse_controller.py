from services.tenant_service import tenant_query, tenant_get_or_404
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from extensions import db
from models.inventory_item import InventoryItem
from models.service import Service
from services import audit_service
from services import inventory_batch_service
from models.inventory_batch import InventoryBatch
from decorators import admin_required
from datetime import datetime

warehouse_bp = Blueprint('warehouse', __name__)


def _classify_item_group(name):
    text = (name or '').lower()
    groups = {
        'beverage': ['nước', 'nuoc', 'bia', 'coca', 'pepsi', 'redbull', 'sting', 'trà', 'tra', 'coffee', 'cà phê', 'caphe', 'lavie', 'aquafina'],
        'food': ['mỳ', 'mi ', 'mì', 'pho ', 'phở', 'snack', 'bánh', 'banh', 'kẹo', 'keo', 'xúc xích', 'xuc xich', 'đồ ăn', 'do an'],
        'amenity': ['khăn', 'khan', 'bàn chải', 'ban chai', 'kem đánh răng', 'kem danh rang', 'dầu gội', 'dau goi', 'sữa tắm', 'sua tam', 'xà phòng', 'xa phong', 'ly ', 'cốc', 'coc'],
    }

    for group, keywords in groups.items():
        if any(k in text for k in keywords):
            return group
    return None


def _validate_service_link(item_name, service_id):
    if not service_id:
        return True, ''

    service = tenant_query(Service).filter_by(id=service_id).first()
    if not service:
        return False, 'Dịch vụ liên kết không tồn tại.'

    item_group = _classify_item_group(item_name)
    service_group = _classify_item_group(service.name)

    # Chỉ chặn khi nhận diện được cả 2 nhóm và nhóm khác nhau.
    if item_group and service_group and item_group != service_group:
        return False, f"Liên kết sai nhóm: vật tư '{item_name}' không phù hợp với dịch vụ '{service.name}'."

    return True, ''

# --- VIEW ---
@warehouse_bp.route('/warehouse')
@login_required
def index():
    return render_template('warehouse/index.html')

# --- API: LẤY DANH SÁCH ---
@warehouse_bp.route('/api/warehouse')
@login_required
def get_items():
    items = tenant_query(InventoryItem).order_by(InventoryItem.id.desc()).all()
    return jsonify([item.to_dict() for item in items])

# --- API: THÊM MỚI ---
@warehouse_bp.route('/api/warehouse', methods=['POST'])
@login_required
@admin_required
def add_item():
    try:
        data = request.get_json()
        service_id = data.get('service_id') or None
        ok, msg = _validate_service_link(data.get('name'), service_id)
        if not ok:
            return jsonify({'success': False, 'msg': msg})

        new_item = InventoryItem(
            code=data['code'],
            name=data['name'],
            unit=data.get('unit', 'cái'),
            quantity=int(data.get('quantity', 0)),
            min_quantity=int(data.get('min_quantity', 10)),
            price=float(data.get('price', 0)),
            service_id=service_id
        )
        initial_quantity = int(data.get('quantity', 0))
        new_item.quantity = 0
        db.session.add(new_item)
        db.session.flush()
        if initial_quantity > 0:
            inventory_batch_service.create_receipt_batch(
                item=new_item, quantity=initial_quantity,
                received_at=datetime.strptime(data.get('received_at') or datetime.today().strftime('%Y-%m-%d'), '%Y-%m-%d').date(),
                expires_at=datetime.strptime(data['expires_at'], '%Y-%m-%d').date() if data.get('expires_at') else None,
                unit_cost=float(data.get('price', 0)), actor_user_id=current_user.id,
            )
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Thêm vật tư thành công!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': f'Lỗi: {str(e)}'})

# --- API: CẬP NHẬT ---
@warehouse_bp.route('/api/warehouse/<int:item_id>', methods=['PUT'])
@login_required
@admin_required
def update_item(item_id):
    try:
        data = request.get_json()
        item = tenant_query(InventoryItem).filter_by(id=item_id).first()
        if not item:
            return jsonify({'success': False, 'msg': 'Không tìm thấy vật tư!'})

        before_data = {
            'code': item.code,
            'name': item.name,
            'quantity': int(item.quantity or 0),
            'price': float(item.price or 0),
            'service_id': item.service_id,
        }

        service_id = data.get('service_id') or None
        item_name = data.get('name', item.name)
        ok, msg = _validate_service_link(item_name, service_id)
        if not ok:
            return jsonify({'success': False, 'msg': msg})
        
        item.code = data.get('code', item.code)
        item.name = item_name
        item.unit = data.get('unit', item.unit)
        item.min_quantity = int(data.get('min_quantity', item.min_quantity))
        item.price = float(data.get('price', item.price))
        item.service_id = service_id
        audit_service.record_event(
            hotel_id=item.hotel_id,
            actor_user_id=current_user.id,
            action='update_inventory',
            entity_type='inventory_item',
            entity_id=item.id,
            before_data=before_data,
            after_data={
                'code': item.code,
                'name': item.name,
                'quantity': int(item.quantity or 0),
                'price': float(item.price or 0),
                'service_id': item.service_id,
            },
        )
        
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Cập nhật thành công!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': f'Lỗi: {str(e)}'})

# --- API: NHẬP THÊM KHO ---
@warehouse_bp.route('/api/warehouse/<int:item_id>/restock', methods=['POST'])
@login_required
@admin_required
def restock_item(item_id):
    try:
        data = request.get_json()
        qty = int(data.get('quantity', 0))
        if qty <= 0:
            return jsonify({'success': False, 'msg': 'Số lượng nhập phải > 0'})
        
        item = tenant_query(InventoryItem).filter_by(id=item_id).first()
        if not item:
            return jsonify({'success': False, 'msg': 'Không tìm thấy vật tư!'})
        
        received_at = datetime.strptime(data.get('received_at') or datetime.today().strftime('%Y-%m-%d'), '%Y-%m-%d').date()
        expires_at = datetime.strptime(data['expires_at'], '%Y-%m-%d').date() if data.get('expires_at') else None
        batch = inventory_batch_service.create_receipt_batch(
            item=item, quantity=qty, received_at=received_at, expires_at=expires_at,
            unit_cost=float(data.get('unit_cost', item.price or 0)), actor_user_id=current_user.id,
        )
        audit_service.record_event(
            hotel_id=item.hotel_id,
            actor_user_id=current_user.id,
            action='restock_inventory',
            entity_type='inventory_item',
            entity_id=item.id,
            before_data={'quantity': int(item.quantity or 0) - qty},
            after_data={'quantity': int(item.quantity)},
        )
        db.session.commit()
        return jsonify({'success': True, 'msg': f'Đã nhập thêm {qty} {item.unit} {item.name}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(e)})

# --- API: XÓA ---
@warehouse_bp.route('/api/warehouse/<int:item_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_item(item_id):
    try:
        item = tenant_query(InventoryItem).filter_by(id=item_id).first()
        if not item:
            return jsonify({'success': False, 'msg': 'Không tìm thấy!'})
        if item.batches or item.movements:
            return jsonify({'success': False, 'msg': 'Không thể xóa vật tư đã có lịch sử kho.'}), 409
        audit_service.record_event(
            hotel_id=item.hotel_id,
            actor_user_id=current_user.id,
            action='delete_inventory',
            entity_type='inventory_item',
            entity_id=item.id,
            before_data={
                'code': item.code,
                'name': item.name,
                'quantity': int(item.quantity or 0),
            },
        )
        db.session.delete(item)
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Đã xóa!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(e)})


@warehouse_bp.route('/api/warehouse/<int:item_id>/batches')
@login_required
def get_batches(item_id):
    item = tenant_get_or_404(InventoryItem, item_id)
    return jsonify([{
        'id': batch.id, 'batch_code': batch.batch_code, 'received_at': batch.received_at.isoformat(),
        'expires_at': batch.expires_at.isoformat() if batch.expires_at else None,
        'quantity_available': batch.quantity_available, 'status': batch.status,
    } for batch in item.batches])


@warehouse_bp.route('/api/warehouse/batches/<int:batch_id>/dispose', methods=['POST'])
@login_required
@admin_required
def dispose_batch(batch_id):
    data = request.get_json() or {}
    batch = tenant_query(InventoryBatch).filter_by(id=batch_id).first()
    if not batch:
        return jsonify({'success': False, 'msg': 'Không tìm thấy lô hàng.'}), 404
    try:
        inventory_batch_service.dispose_batch(
            batch=batch, quantity=data.get('quantity'), reason=data.get('reason'),
            note=data.get('note'), actor_user_id=current_user.id, hotel_id=batch.hotel_id,
        )
        audit_service.record_event(hotel_id=batch.hotel_id, actor_user_id=current_user.id,
            action='dispose_inventory', entity_type='inventory_batch', entity_id=batch.id,
            after_data={'quantity': data.get('quantity'), 'reason': data.get('reason')})
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Đã ghi nhận hủy hàng.'})
    except ValueError as error:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(error)}), 400
