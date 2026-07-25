from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import User  # Nhớ import model User mới
from urllib.parse import urlparse

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # 1. Nếu đã đăng nhập rồi thì đá về trang chủ luôn, không cho vào trang login nữa
    if current_user.is_authenticated:
        return redirect(url_for('room.map_view')) # Hoặc trang dashboard của bạn

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        from sqlalchemy import or_
        from flask import g
        
        # 2. Tìm user trong DB
        user = User.query.filter(
            User.username == username,
            or_(User.hotel_id == g.hotel_id, User.is_super_admin == True)
        ).first()

        # 3. Kiểm tra user tồn tại VÀ mật khẩu đúng
        if not user or not user.check_password(password):
            flash('Tên đăng nhập hoặc mật khẩu không đúng.', 'danger')
            return redirect(url_for('auth.login'))
        
        # 3b. KIỂM TRA TENANT (User phải thuộc khách sạn này hoặc là super admin)
        from flask import g
        if not user.is_super_admin and user.hotel_id != g.hotel_id:
            flash('Tài khoản của bạn không thuộc khách sạn này.', 'warning')
            return redirect(url_for('auth.login'))
        
        # 4. Thực hiện đăng nhập
        login_user(user, remember=remember)

        # 5. Xử lý chuyển hướng
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('room.map_view')
            
        return redirect(next_page)

    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Bạn đã đăng xuất thành công.', 'info')
    return redirect(url_for('auth.login'))