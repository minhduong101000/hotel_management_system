from services.tenant_service import tenant_query, tenant_get_or_404
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from extensions import db
from models.room import Room
from models.price_rule import PriceRule
from datetime import datetime
from services import audit_service
from services.room_configuration_service import (
    RoomConfigurationValidationError,
    validate_default_rate_update_payload,
)

price_bp = Blueprint('price', __name__)

# --- VIEW ---
@price_bp.route('/admin/price-manager')
@login_required
def index():
    return render_template('admin/price_manager.html')

# ========================================================
# API 1: LẤY DỮ LIỆU (Mapping từ DB -> JSON Frontend)
# ========================================================
@price_bp.route('/api/prices/all-data')
@login_required
def get_all_data():
    try:
        # A. Lấy giá Base của Phòng
        rooms = tenant_query(Room).all()
        rooms_data = []
        for r in rooms:
            rooms_data.append({
                'id': r.id,
                'number': r.room_number,
                'type': r.room_type,
                'price_daily': float(r.price_per_night or 0),
                
                # --- SỬA: Map đúng cột DB của bạn sang key JSON mà JS đang chờ ---
                # DB: price_initial_block -> JSON: price_initial
                'price_initial': float(r.price_initial_block or 0), 
                
                # DB: price_next_hour -> JSON: price_next
                'price_next': float(r.price_next_hour or 0),
                
                # (Tùy chọn) Gửi thêm số giờ block đầu nếu sau này cần hiển thị
                'initial_hours': r.initial_hours 
            })

        # B. Lấy danh sách Luật giá
        # LƯU Ý: Bạn cần đảm bảo model PriceRule cũng có các cột tương ứng
        # Nếu PriceRule chưa đổi tên cột, hãy sửa model PriceRule giống Room
        rules = tenant_query(PriceRule).order_by(PriceRule.priority.desc()).all()
        rules_data = []
        for rule in rules:
            # Kiểm tra xem PriceRule dùng tên cột nào (giả sử bạn đã đồng bộ tên cột với Room)
            # Nếu PriceRule vẫn dùng tên cũ, hãy sửa lại đoạn getattr bên dưới
            p_init = getattr(rule, 'price_initial_block', getattr(rule, 'price_initial', 0))
            p_next = getattr(rule, 'price_next_hour', getattr(rule, 'price_next', 0))

            rules_data.append({
                'id': rule.id,
                'name': rule.name,
                'room_type': rule.room_type,
                'priority': rule.priority,
                'start_date': rule.start_date.strftime('%Y-%m-%d') if rule.start_date else '',
                'end_date': rule.end_date.strftime('%Y-%m-%d') if rule.end_date else '',
                'days_of_week': rule.days_of_week if rule.days_of_week else '',
                
                'price_daily': float(rule.price_daily or 0),
                'price_initial': float(p_init or 0),
                'price_next': float(p_next or 0)
            })

        return jsonify({'rooms': rooms_data, 'rules': rules_data})
    except Exception as e:
        print(f"Error fetching price data: {e}")
        return jsonify({'error': str(e)}), 500

# ========================================================
# API 2: CẬP NHẬT GIÁ BASE (Mapping từ JSON Frontend -> DB)
# ========================================================
@price_bp.route('/api/prices/update-base', methods=['POST'])
@login_required
def update_base_price():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            'success': False,
            'error_code': 'validation_error',
            'errors': {'request': 'Dữ liệu gửi lên phải là một đối tượng JSON.'},
        }), 400

    try:
        room_id = int(data.get('id'))
    except (TypeError, ValueError):
        return jsonify({
            'success': False,
            'error_code': 'validation_error',
            'errors': {'id': 'ID phòng không hợp lệ.'},
        }), 400

    room = tenant_query(Room).filter_by(id=room_id).first()
    if not room:
        return jsonify({'success': False, 'msg': 'Không tìm thấy phòng'}), 404

    try:
        values = validate_default_rate_update_payload(data, room.initial_hours)
    except RoomConfigurationValidationError as exc:
        return jsonify({
            'success': False,
            'error_code': 'validation_error',
            'errors': exc.errors,
        }), 400

    try:
        before_data = {
            'price_daily': float(room.price_per_night or 0),
            'price_initial': float(room.price_initial_block or 0),
            'price_next': float(room.price_next_hour or 0),
            'initial_hours': int(room.initial_hours or 0),
        }

        room.price_per_night = values['price_per_night']
        room.price_initial_block = values['price_initial_block']
        room.initial_hours = values['initial_hours']
        room.price_next_hour = values['price_next_hour']

        audit_service.record_event(
            hotel_id=room.hotel_id,
            actor_user_id=current_user.id,
            action='update_base_price',
            entity_type='room',
            entity_id=room.id,
            before_data=before_data,
            after_data={
                'price_daily': float(room.price_per_night or 0),
                'price_initial': float(room.price_initial_block or 0),
                'price_next': float(room.price_next_hour or 0),
                'initial_hours': int(room.initial_hours or 0),
                'price_per_night': float(room.price_per_night or 0),
                'price_initial_block': float(room.price_initial_block or 0),
                'price_next_hour': float(room.price_next_hour or 0),
            },
        )
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Đã cập nhật giá phòng!'})
    except Exception:
        db.session.rollback()
        raise

# ========================================================
# API 3: LƯU LUẬT GIÁ
# ========================================================
@price_bp.route('/api/prices/save-rule', methods=['POST'])
@login_required
def save_rule():
    try:
        data = request.get_json()
        rule_id = data.get('id')
        
        # Xử lý ngày tháng
        start_date = datetime.strptime(data['start_date'], '%Y-%m-%d') if data.get('start_date') else None
        end_date = datetime.strptime(data['end_date'], '%Y-%m-%d') if data.get('end_date') else None
        if start_date and end_date and end_date < start_date:
            return jsonify({'success': False, 'msg': 'Ngày kết thúc phải từ ngày bắt đầu trở đi.'}), 400
        
        days_str = None
        if data.get('days_of_week') and len(data['days_of_week']) > 0:
            days_str = ",".join(map(str, data['days_of_week']))

        # CHỈ LẤY GIÁ NGÀY
        val_daily = float(data.get('price_daily', 0))
        if val_daily <= 0:
            return jsonify({'success': False, 'msg': 'Giá qua đêm phải lớn hơn 0.'}), 400

        if rule_id:
            # === UPDATE ===
            rule = tenant_query(PriceRule).filter_by(id=rule_id).first()
            if not rule: return jsonify({'success': False, 'msg': 'Lỗi ID'})
            before_data = {'name': rule.name, 'price_daily': float(rule.price_daily or 0)}
            
            rule.name = data['name']
            rule.room_type = data['room_type']
            rule.priority = int(data['priority'])
            rule.start_date = start_date
            rule.end_date = end_date
            rule.days_of_week = days_str
            rule.price_daily = val_daily
            audit_service.record_event(
                hotel_id=rule.hotel_id, actor_user_id=current_user.id,
                action='update_price_rule', entity_type='price_rule', entity_id=rule.id,
                before_data=before_data,
                after_data={'name': rule.name, 'price_daily': float(rule.price_daily or 0)},
            )
            # Không cập nhật giá giờ nữa

        else:
            # === CREATE ===
            new_rule = PriceRule(
                name=data['name'],
                room_type=data['room_type'],
                priority=int(data['priority']),
                start_date=start_date,
                end_date=end_date,
                days_of_week=days_str,
                is_active=True,
                price_daily=val_daily
                # Không truyền price_initial/next vào đây nữa -> HẾT LỖI
            )
            db.session.add(new_rule)
            db.session.flush()
            audit_service.record_event(
                hotel_id=new_rule.hotel_id,
                actor_user_id=current_user.id,
                action='create_price_rule',
                entity_type='price_rule',
                entity_id=new_rule.id,
                after_data={
                    'name': new_rule.name,
                    'room_type': new_rule.room_type,
                    'priority': new_rule.priority,
                    'price_daily': float(new_rule.price_daily or 0),
                },
            )
        
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Lưu luật giá thành công!'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")
        return jsonify({'success': False, 'msg': f"Lỗi: {str(e)}"})

# ========================================================
# API 4: XÓA LUẬT
# ========================================================
@price_bp.route('/api/prices/delete-rule/<int:id>', methods=['DELETE'])
@login_required
def delete_rule(id):
    try:
        rule = tenant_query(PriceRule).filter_by(id=id).first()
        if rule:
            audit_service.record_event(
                hotel_id=rule.hotel_id,
                actor_user_id=current_user.id,
                action='delete_price_rule',
                entity_type='price_rule',
                entity_id=rule.id,
                before_data={
                    'name': rule.name,
                    'room_type': rule.room_type,
                    'priority': rule.priority,
                    'price_daily': float(rule.price_daily or 0),
                },
            )
            db.session.delete(rule)
            db.session.commit()
            return jsonify({'success': True, 'msg': 'Đã xóa luật!'})
        return jsonify({'success': False, 'msg': 'ID không tồn tại'})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})
