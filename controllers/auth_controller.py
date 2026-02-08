from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from models.user import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        print(f"--- DEBUG LOGIN ---")
        print(f"Input Username: {username}")
        print(f"Input Password: {password}")

        user = User.query.filter_by(username=username).first()
        
        if user:
            print(f"User found in DB: ID={user.id}, Hash={user.password_hash}")
            is_valid = user.check_password(password)
            print(f"Password Check Result: {is_valid}")
            
            if is_valid:
                login_user(user)
                flash('Đăng nhập thành công!', 'success')
                return redirect(url_for('dashboard.timeline_view'))
        else:
            print("User NOT found in DB")

        flash('Sai tài khoản hoặc mật khẩu.', 'danger')
            
    return render_template('auth/login.html')