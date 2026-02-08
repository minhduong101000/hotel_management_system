from flask import Blueprint, render_template
from flask_login import login_required

setting_bp = Blueprint('setting', __name__)

@setting_bp.route('/settings')
@login_required
def index():
    settings_list = [
        {'name': 'Quản lý Loại phòng', 'desc': 'Thêm sửa xóa loại phòng và giá', 'icon': 'fa-bed'},
        {'name': 'Quản lý Nhân viên', 'desc': 'Tạo tài khoản và phân quyền', 'icon': 'fa-users-cog'},
        {'name': 'Thông tin Khách sạn', 'desc': 'Tên, địa chỉ, logo, hotline', 'icon': 'fa-hotel'},
        {'name': 'Cấu hình In hóa đơn', 'desc': 'Mẫu in, khổ giấy', 'icon': 'fa-print'},
    ]
    return render_template('settings/index.html', settings=settings_list)