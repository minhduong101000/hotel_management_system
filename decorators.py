from functools import wraps
from flask import abort, flash, jsonify, redirect, url_for
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Nếu chưa đăng nhập HOẶC role không phải admin -> Đá ra ngoài
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash("Bạn không có quyền truy cập khu vực này!", "error")
            return redirect(url_for('room.map_view'))
        return f(*args, **kwargs)
    return decorated_function


def master_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.is_super_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def booking_reschedule_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        can_reschedule = (
            current_user.is_authenticated
            and (current_user.role == "admin" or current_user.is_super_admin)
        )
        if not can_reschedule:
            return jsonify(
                {
                    "success": False,
                    "error_code": "forbidden",
                    "msg": "Bạn không có quyền dời lịch booking.",
                }
            ), 403
        return f(*args, **kwargs)

    return decorated_function


def room_structure_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        can_manage_room_structure = (
            current_user.is_authenticated
            and (current_user.role == "admin" or current_user.is_super_admin)
        )
        if not can_manage_room_structure:
            return jsonify(
                {
                    "success": False,
                    "error_code": "forbidden",
                    "msg": "Bạn không có quyền quản lý cấu trúc phòng.",
                }
            ), 403
        return f(*args, **kwargs)

    return decorated_function
