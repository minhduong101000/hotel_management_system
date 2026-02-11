from flask import Flask, redirect, url_for
# Import db và login_manager từ file extensions (nơi bạn khởi tạo chúng)
from extensions import db, login_manager 
from models import User

# Import các Controllers (Blueprints)
from controllers.auth_controller import auth_bp
from controllers.billing_controller import billing_bp
from controllers.customer_controller import customer_bp
from controllers.room_controller import room_bp
from controllers.timeline_controller import timeline_bp
from controllers.service_controller import service_bp
from controllers.warehouse_controller import warehouse_bp
from controllers.staff_controller import staff_bp
from controllers.report_controller import report_bp
from controllers.price_controller import price_bp
from controllers.booking_controller import booking_bp

app = Flask(__name__)

# --- 1. CẤU HÌNH APP ---
app.config['SECRET_KEY'] = 'luxury-secret-key' # Nên đổi chuỗi này phức tạp hơn khi chạy thật
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:123456@localhost/Hotel_Management_System'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- 2. KHỞI TẠO EXTENSIONS ---
db.init_app(app)
login_manager.init_app(app)

# --- [QUAN TRỌNG] CẤU HÌNH LOGIN MANAGER ---
# Đường dẫn đến hàm login (tên blueprint.tên hàm)
login_manager.login_view = 'auth.login' 
login_manager.login_message = "Vui lòng đăng nhập để tiếp tục."

@login_manager.user_loader
def load_user(user_uniquifier):
    """
    Hàm này cực kỳ quan trọng cho bảo mật.
    Nó tìm user dựa trên chuỗi `fs_uniquifier` thay vì ID.
    Nếu Admin đổi mật khẩu -> chuỗi này đổi -> Session cũ vô hiệu -> Logout máy khác.
    """
    return User.query.filter_by(fs_uniquifier=user_uniquifier).first()

# --- 3. ĐĂNG KÝ BLUEPRINTS ---
app.register_blueprint(auth_bp)
app.register_blueprint(customer_bp)
app.register_blueprint(room_bp)
app.register_blueprint(timeline_bp)
app.register_blueprint(service_bp)
app.register_blueprint(billing_bp)
app.register_blueprint(warehouse_bp)
app.register_blueprint(staff_bp)
app.register_blueprint(report_bp)
app.register_blueprint(price_bp)
app.register_blueprint(booking_bp)

# --- 4. ROUTES HỆ THỐNG ---
@app.route('/')
def index():
    # Chuyển hướng về trang sơ đồ phòng sau khi vào trang chủ
    return redirect(url_for('room.map_view')) 


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # 1. Tạo Admin
        if not User.query.filter_by(username='admin').first():
            # Bỏ full_name đi, chỉ giữ lại các trường có trong model
            admin = User(username='admin', role='admin')
            admin.set_password('admin123') 
            db.session.add(admin)
            print(">>> Đã tạo tài khoản: admin / admin123")

        # 2. Tạo Staff 1
        if not User.query.filter_by(username='staff1').first():
            staff1 = User(username='staff1', role='staff')
            staff1.set_password('staff123')
            db.session.add(staff1)
            print(">>> Đã tạo tài khoản: staff1 / staff123")

        # 3. Lưu vào database
        db.session.commit()
        print("--- Hoàn tất khởi tạo ---")

    app.run(debug=True)