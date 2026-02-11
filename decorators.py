from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Nếu chưa đăng nhập HOẶC role không phải admin -> Đá ra ngoài
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash("Bạn không có quyền truy cập khu vực này!", "error")
            return redirect(url_for('room.index')) # Chuyển về trang sơ đồ phòng
        return f(*args, **kwargs)
    return decorated_function