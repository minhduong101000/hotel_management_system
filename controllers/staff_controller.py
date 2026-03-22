from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from decorators import admin_required
from extensions import db
from models import User

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')

@staff_bp.route('/', methods=['GET', 'POST'])
@login_required
@admin_required
def index():

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')

        # Kiểm tra trùng tên đăng nhập
        if User.query.filter_by(username=username).first():
            flash('Tên đăng nhập đã tồn tại!', 'error')
        else:
            # Tạo user mới (Chỉ lấy username, password, role)
            new_user = User(username=username, role=role)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('Thêm nhân viên thành công!', 'success')
            return redirect(url_for('staff.index'))

    # Lấy danh sách, sắp xếp Staff lên trước Admin để dễ nhìn
    users = User.query.order_by(User.role.desc()).all()
    return render_template('staff/index.html', users=users)

@staff_bp.route('/reset-password/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def reset_password(user_id):
        
    new_password = request.form.get('new_password')
    user = User.query.get_or_404(user_id)
    
    if new_password:
        user.set_password(new_password)
        db.session.commit()
        flash(f'Đã đổi mật khẩu cho {user.username}', 'success')
    
    return redirect(url_for('staff.index'))

@staff_bp.route('/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):

    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Không thể xóa chính mình!', 'error')
    else:
        db.session.delete(user)
        db.session.commit()
        flash('Đã xóa nhân viên!', 'success')
        
    return redirect(url_for('staff.index'))