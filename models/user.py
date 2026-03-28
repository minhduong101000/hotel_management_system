from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

class User(UserMixin, db.Model):
    __tablename__ = 'users' # Tên bảng trong database

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='staff') # 'admin' hoặc 'staff'
    
    # Multi-tenant fields
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=True)
    is_super_admin = db.Column(db.Boolean, default=False)
    
    # Cột này dùng để xử lý việc "Đăng xuất từ xa"
    # Mỗi khi đổi mật khẩu, ta sẽ tạo lại mã mới cho cột này
    fs_uniquifier = db.Column(db.String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))

    def set_password(self, password):
        """
        Hàm này làm 2 việc:
        1. Mã hóa mật khẩu.
        2. Thay đổi fs_uniquifier -> Khiến các cookie cũ ở máy khác bị vô hiệu hóa ngay lập tức.
        """
        self.password_hash = generate_password_hash(password)
        self.fs_uniquifier = str(uuid.uuid4()) 

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Ghi đè phương thức get_id của Flask-Login
    # Để hệ thống theo dõi user qua chuỗi bảo mật thay vì ID
    def get_id(self):
        return self.fs_uniquifier