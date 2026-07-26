from services.tenant_service import tenant_query, tenant_get_or_404
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from decorators import admin_required
from extensions import db
from models.expense import Expense
from models.inventory_item import InventoryItem
from models.service import Service
from datetime import datetime
import re
from services import audit_service

expense_bp = Blueprint('expense', __name__)


def _extract_inventory_code(text):
    if not text:
        return None
    m = re.search(r'\[KHO:([^\]]+)\]', str(text))
    return m.group(1).strip() if m else None


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

    if item_group and service_group and item_group != service_group:
        return False, f"Liên kết sai nhóm: vật tư '{item_name}' không phù hợp với dịch vụ '{service.name}'."

    return True, ''

# --- VIEW ---
@expense_bp.route('/expenses')
@login_required
@admin_required
def index():
    return render_template('reports/expenses.html')

# --- API: LẤY DANH SÁCH ---
@expense_bp.route('/api/expenses')
@login_required
@admin_required
def get_expenses():
    try:
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        category = request.args.get('category')
        
        query = tenant_query(Expense)
        
        if start_str:
            query = query.filter(Expense.expense_date >= datetime.strptime(start_str, '%Y-%m-%d').date())
        if end_str:
            query = query.filter(Expense.expense_date <= datetime.strptime(end_str, '%Y-%m-%d').date())
        if category:
            query = query.filter(Expense.category == category)
        
        expenses = query.order_by(Expense.expense_date.desc(), Expense.id.desc()).all()
        
        total = sum(float(e.amount or 0) for e in expenses)
        
        data = []
        for e in expenses:
            row = e.to_dict()
            inv_code = _extract_inventory_code(e.description)
            row['inventory_code'] = inv_code
            row['inventory_name'] = None
            row['inventory_service_name'] = None
            if inv_code:
                inv_item = tenant_query(InventoryItem).filter_by(code=inv_code).first()
                if inv_item:
                    row['inventory_name'] = inv_item.name
                    row['inventory_service_name'] = inv_item.service.name if inv_item.service else None
            data.append(row)

        return jsonify({
            'success': True,
            'data': data,
            'total': total
        })
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})

# --- API: THÊM MỚI ---
@expense_bp.route('/api/expenses', methods=['POST'])
@login_required
@admin_required
def add_expense():
    try:
        data = request.get_json()
        desc = (data.get('description') or '').strip()

        new_expense = Expense(
            category=data['category'],
            description=desc,
            amount=float(data['amount']),
            expense_date=datetime.strptime(data['expense_date'], '%Y-%m-%d').date(),
            created_by=current_user.id
        )
        db.session.add(new_expense)

        # Tuy chon: dong bo vao kho ngay khi nhap chi phi
        sync_inventory = bool(data.get('sync_inventory', False))
        sync_service = bool(data.get('sync_service', False))
        service_payload = data.get('service') or {}
        warehouse = data.get('warehouse') or {}
        if sync_inventory:
            item_code = (warehouse.get('code') or '').strip()
            item_name = (warehouse.get('name') or '').strip()
            unit = (warehouse.get('unit') or 'cái').strip()
            qty = int(warehouse.get('quantity') or 0)
            min_qty = int(warehouse.get('min_quantity') or 10)
            service_id = warehouse.get('service_id') or None

            if sync_service:
                service_name = (service_payload.get('name') or '').strip()
                service_price = float(service_payload.get('price') or 0)

                # Nếu đã chọn service_id thì cập nhật service đó. Nếu chưa có thì tạo service mới.
                if service_id:
                    service_obj = tenant_query(Service).filter_by(id=service_id).first()
                    if not service_obj:
                        return jsonify({'success': False, 'msg': 'Dịch vụ để đồng bộ không tồn tại.'})

                    if service_name:
                        service_obj.name = service_name
                    if service_price > 0:
                        service_obj.price = int(round(service_price))

                    service_id = service_obj.id
                else:
                    if not service_name:
                        service_name = item_name
                    if service_price <= 0:
                        service_price = float(data['amount']) / qty if qty > 0 else 0

                    if service_price <= 0:
                        return jsonify({'success': False, 'msg': 'Giá dịch vụ phải lớn hơn 0 khi đồng bộ dịch vụ.'})

                    existing_service = tenant_query(Service).filter_by(name=service_name).first()
                    if existing_service:
                        existing_service.price = int(round(service_price))
                        service_id = existing_service.id
                    else:
                        new_service = Service(name=service_name, price=int(round(service_price)))
                        db.session.add(new_service)
                        db.session.flush()
                        service_id = new_service.id

            ok, msg = _validate_service_link(item_name, service_id)
            if not ok:
                return jsonify({'success': False, 'msg': msg})

            if not item_code or not item_name:
                return jsonify({'success': False, 'msg': 'Thiếu mã hoặc tên vật tư để cập nhật kho.'})
            if qty <= 0:
                return jsonify({'success': False, 'msg': 'Số lượng nhập kho phải lớn hơn 0.'})

            item = tenant_query(InventoryItem).filter_by(code=item_code).first()
            if item:
                item.name = item_name
                item.unit = unit or item.unit
                item.quantity = int(item.quantity or 0) + qty
                item.min_quantity = min_qty
                item.price = float(data['amount']) / qty if qty > 0 else item.price
                item.service_id = service_id
            else:
                item = InventoryItem(
                    code=item_code,
                    name=item_name,
                    unit=unit,
                    quantity=qty,
                    min_quantity=min_qty,
                    price=float(data['amount']) / qty if qty > 0 else 0,
                    service_id=service_id
                )
                db.session.add(item)

            marker = f"[KHO:{item_code}]"
            if marker not in new_expense.description:
                if new_expense.description:
                    new_expense.description = f"{new_expense.description} {marker}"
                else:
                    new_expense.description = marker

        db.session.flush()
        audit_service.record_event(
            hotel_id=new_expense.hotel_id,
            actor_user_id=current_user.id,
            action='create_expense',
            entity_type='expense',
            entity_id=new_expense.id,
            after_data={
                'category': new_expense.category,
                'description': new_expense.description,
                'amount': float(new_expense.amount or 0),
                'expense_date': new_expense.expense_date.isoformat(),
            },
        )
        db.session.commit()
        msg = 'Thêm chi phí thành công!'
        if sync_inventory:
            msg += ' Kho hàng đã được cập nhật.'
        if sync_inventory and sync_service:
            msg += ' Dịch vụ cũng đã được đồng bộ.'
        return jsonify({'success': True, 'msg': msg})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': f'Lỗi: {str(e)}'})

# --- API: XÓA ---
@expense_bp.route('/api/expenses/<int:expense_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_expense(expense_id):
    try:
        expense = tenant_query(Expense).filter_by(id=expense_id).first()
        if not expense:
            return jsonify({'success': False, 'msg': 'Không tìm thấy!'})
        audit_service.record_event(
            hotel_id=expense.hotel_id,
            actor_user_id=current_user.id,
            action='delete_expense',
            entity_type='expense',
            entity_id=expense.id,
            before_data={
                'category': expense.category,
                'description': expense.description,
                'amount': float(expense.amount or 0),
                'expense_date': expense.expense_date.isoformat(),
            },
        )
        db.session.delete(expense)
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Đã xóa chi phí!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(e)})
