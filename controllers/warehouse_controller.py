from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from extensions import db
from models.inventory_item import InventoryItem
from models.service import Service

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

    service = Service.query.get(service_id)
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
    items = InventoryItem.query.order_by(InventoryItem.id.desc()).all()
    return jsonify([item.to_dict() for item in items])

# --- API: THÊM MỚI ---
@warehouse_bp.route('/api/warehouse', methods=['POST'])
@login_required
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
        db.session.add(new_item)
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Thêm vật tư thành công!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': f'Lỗi: {str(e)}'})

# --- API: CẬP NHẬT ---
@warehouse_bp.route('/api/warehouse/<int:item_id>', methods=['PUT'])
@login_required
def update_item(item_id):
    try:
        data = request.get_json()
        item = InventoryItem.query.get(item_id)
        if not item:
            return jsonify({'success': False, 'msg': 'Không tìm thấy vật tư!'})

        service_id = data.get('service_id') or None
        item_name = data.get('name', item.name)
        ok, msg = _validate_service_link(item_name, service_id)
        if not ok:
            return jsonify({'success': False, 'msg': msg})
        
        item.code = data.get('code', item.code)
        item.name = item_name
        item.unit = data.get('unit', item.unit)
        item.quantity = int(data.get('quantity', item.quantity))
        item.min_quantity = int(data.get('min_quantity', item.min_quantity))
        item.price = float(data.get('price', item.price))
        item.service_id = service_id
        
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Cập nhật thành công!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': f'Lỗi: {str(e)}'})

# --- API: NHẬP THÊM KHO ---
@warehouse_bp.route('/api/warehouse/<int:item_id>/restock', methods=['POST'])
@login_required
def restock_item(item_id):
    try:
        data = request.get_json()
        qty = int(data.get('quantity', 0))
        if qty <= 0:
            return jsonify({'success': False, 'msg': 'Số lượng nhập phải > 0'})
        
        item = InventoryItem.query.get(item_id)
        if not item:
            return jsonify({'success': False, 'msg': 'Không tìm thấy vật tư!'})
        
        item.quantity += qty
        db.session.commit()
        return jsonify({'success': True, 'msg': f'Đã nhập thêm {qty} {item.unit} {item.name}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(e)})

# --- API: XÓA ---
@warehouse_bp.route('/api/warehouse/<int:item_id>', methods=['DELETE'])
@login_required
def delete_item(item_id):
    try:
        item = InventoryItem.query.get(item_id)
        if not item:
            return jsonify({'success': False, 'msg': 'Không tìm thấy!'})
        db.session.delete(item)
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Đã xóa!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(e)})