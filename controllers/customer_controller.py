from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from sqlalchemy import or_  # Cần cái này để tìm kiếm OR (Hoặc tên, Hoặc sđt...)
from extensions import db
from models.customer import Customer

customer_bp = Blueprint('customer', __name__)

# 1. GIAO DIỆN (View)
@customer_bp.route('/customers')
@login_required
def index():
    return render_template('customers/index.html')

# 2. API LẤY DANH SÁCH & TÌM KIẾM
@customer_bp.route('/api/customers')
@login_required
def get_customers():
    keyword = request.args.get('q', '').strip() # Lấy từ khóa tìm kiếm
    
    query = Customer.query
    
    if keyword:
        # Logic tìm kiếm: Tìm trong Tên HOẶC SĐT HOẶC CCCD
        search_filter = or_(
            Customer.name.ilike(f'%{keyword}%'),   # ilike là tìm không phân biệt hoa thường
            Customer.phone.ilike(f'%{keyword}%'),
            Customer.cccd.ilike(f'%{keyword}%')
        )
        query = query.filter(search_filter)
    
    # Sắp xếp người mới nhất lên đầu
    customers = query.order_by(Customer.id.desc()).limit(100).all()
    
    return jsonify([c.to_dict() for c in customers])

# 3. API THÊM MỚI
@customer_bp.route('/api/customers', methods=['POST'])
@login_required
def add_customer():
    data = request.get_json()
    try:
        new_cus = Customer(
            name=data['name'],
            phone=data['phone'],
            email=data.get('email'),
            cccd=data.get('cccd'),
            address=data.get('address')
        )
        db.session.add(new_cus)
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Thêm khách hàng thành công!'})
    except Exception as e:
        return jsonify({'success': False, 'msg': 'Lỗi (Có thể trùng SĐT/CCCD): ' + str(e)})

# 4. API CẬP NHẬT
@customer_bp.route('/api/customers/<int:id>', methods=['PUT'])
@login_required
def update_customer(id):
    data = request.get_json()
    cus = Customer.query.get(id)
    if cus:
        try:
            cus.name = data['name']
            cus.phone = data['phone']
            cus.email = data.get('email')
            cus.cccd = data.get('cccd')
            cus.address = data.get('address')
            db.session.commit()
            return jsonify({'success': True, 'msg': 'Cập nhật thành công!'})
        except Exception as e:
            return jsonify({'success': False, 'msg': 'Lỗi trùng lặp dữ liệu!'})
            
    return jsonify({'success': False, 'msg': 'Không tìm thấy khách hàng'})

# 5. API XÓA
@customer_bp.route('/api/customers/<int:id>', methods=['DELETE'])
@login_required
def delete_customer(id):
    cus = Customer.query.get(id)
    if cus:
        db.session.delete(cus)
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Đã xóa khách hàng!'})
    return jsonify({'success': False, 'msg': 'Không tìm thấy khách hàng'})