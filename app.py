from flask import Flask, redirect, url_for, g, abort
from extensions import db, login_manager, mail 
from flask_migrate import Migrate
import warnings
from models import User
from models.inventory_item import InventoryItem
from models.expense import Expense
from models.booking import Booking
from models.booking_room import BookingRoom
from models.hotel import Hotel
from config import Config
from sqlalchemy import inspect, text

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
from controllers.expense_controller import expense_bp
from controllers.cashier_controller import cashier_bp

app = Flask(__name__)

# --- 1. CẤU HÌNH APP ---
app.config.from_object(Config)

# --- 2. KHỞI TẠO EXTENSIONS ---
db.init_app(app)
login_manager.init_app(app)
mail.init_app(app)
migrate = Migrate(app, db)

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

# --- 3. ĐĂNG KÝ BLUEPRINTS VỚI TENANT PREFIX ---
# Tất cả các route nghiệp vụ sẽ có tiền tố /<hotel_slug>/
tenant_prefix = '/<hotel_slug>'

app.register_blueprint(auth_bp, url_prefix=tenant_prefix)
app.register_blueprint(customer_bp, url_prefix=f"{tenant_prefix}/customers")
app.register_blueprint(room_bp, url_prefix=f"{tenant_prefix}/rooms")
app.register_blueprint(timeline_bp, url_prefix=f"{tenant_prefix}/timeline")
app.register_blueprint(service_bp, url_prefix=f"{tenant_prefix}/services")
app.register_blueprint(billing_bp, url_prefix=f"{tenant_prefix}/billing")
app.register_blueprint(warehouse_bp, url_prefix=f"{tenant_prefix}/warehouse")
app.register_blueprint(staff_bp, url_prefix=f"{tenant_prefix}/staff")
app.register_blueprint(report_bp, url_prefix=f"{tenant_prefix}/reports")
app.register_blueprint(price_bp, url_prefix=f"{tenant_prefix}/prices")
app.register_blueprint(booking_bp, url_prefix=f"{tenant_prefix}/bookings")
app.register_blueprint(expense_bp, url_prefix=f"{tenant_prefix}/expenses")
app.register_blueprint(cashier_bp, url_prefix=f"{tenant_prefix}/cashier")

# --- 4. XỬ LÝ ĐA TENANT (URL SLUG) ---

@app.url_value_preprocessor
def pull_hotel_slug(endpoint, values):
    """Lấy hotel_slug từ URL và đưa vào biến toàn cục g."""
    if values and 'hotel_slug' in values:
        g.hotel_slug = values.pop('hotel_slug')
    elif 'hotel_slug' in g:
        pass
    else:
        # Fallback if slug is somehow missing but we are in a tenant route
        pass

@app.url_defaults
def add_language_code(endpoint, values):
    """Auto-inject hotel_slug in url_for(...) and add cache-buster for static files"""
    if 'hotel_slug' in values or not getattr(g, 'hotel_slug', None):
        pass
    else:
        if app.url_map.is_endpoint_expecting(endpoint, 'hotel_slug'):
            values['hotel_slug'] = g.hotel_slug

    # Cache buster for static files
    if endpoint == 'static':
        import time
        values['v'] = int(time.time() / 10) # Change every 10 seconds for dev/testing

@app.context_processor
def inject_hotel_slug():
    """Đảm bảo hotel_slug luôn có sẵn cho template Jinja."""
    return dict(hotel_slug=getattr(g, 'hotel_slug', ''))

@app.before_request
def load_current_hotel():
    """Tải thông tin khách sạn hiện tại dựa trên slug và kiểm tra quyền truy cập."""
    # Bỏ qua các endpoint không cần slug (static, index...)
    if not getattr(g, 'hotel_slug', None):
        return
        
    hotel = Hotel.query.filter_by(slug=g.hotel_slug, is_active=True).first()
    if not hotel:
        abort(404, description="Khách sạn không tồn tại hoặc đã ngừng hoạt động.")
    
    g.current_hotel = hotel
    g.hotel_id = hotel.id

    # RÀO CHẮN BẢO MẬT: Nếu đã login, phải thuộc khách sạn này (hoặc là Super Admin)
    from flask_login import current_user
    if current_user.is_authenticated:
        if not current_user.is_super_admin and current_user.hotel_id != g.hotel_id:
            abort(403, description="Bạn không có quyền truy cập vào khách sạn này.")

# --- 5. ROUTES HỆ THỐNG ---
@app.route('/')
def index():
    # Mặc định chuyển về khách sạn 'central'
    return redirect(url_for('room.map_view', hotel_slug='central')) 


def ensure_schema_updates():
    warnings.warn(
        "ensure_schema_updates() is deprecated; use Flask-Migrate instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    inspector = inspect(db.engine)
    if 'booking_rooms' not in inspector.get_table_names():
        return

    columns = {col['name'] for col in inspector.get_columns('booking_rooms')}
    if 'room_deposit_amount' not in columns:
        db.session.execute(text("ALTER TABLE booking_rooms ADD COLUMN room_deposit_amount NUMERIC(15, 2) DEFAULT 0"))
        db.session.commit()
        print(">>> Đã thêm cột booking_rooms.room_deposit_amount")

    if 'room_deposit_original' not in columns:
        db.session.execute(text("ALTER TABLE booking_rooms ADD COLUMN room_deposit_original NUMERIC(15, 2) DEFAULT 0"))
        db.session.commit()
        print(">>> Đã thêm cột booking_rooms.room_deposit_original")

    if 'cancellation_refund_percent' not in columns:
        db.session.execute(text("ALTER TABLE booking_rooms ADD COLUMN cancellation_refund_percent NUMERIC(5, 2) DEFAULT 0"))
        db.session.commit()
        print(">>> Đã thêm cột booking_rooms.cancellation_refund_percent")

    if 'cancellation_fee_percent' not in columns:
        db.session.execute(text("ALTER TABLE booking_rooms ADD COLUMN cancellation_fee_percent NUMERIC(5, 2) DEFAULT 0"))
        db.session.commit()
        print(">>> Đã thêm cột booking_rooms.cancellation_fee_percent")

    if 'cancellation_refund_amount' not in columns:
        db.session.execute(text("ALTER TABLE booking_rooms ADD COLUMN cancellation_refund_amount NUMERIC(15, 2) DEFAULT 0"))
        db.session.commit()
        print(">>> Đã thêm cột booking_rooms.cancellation_refund_amount")


def backfill_room_deposits():
    bookings = Booking.query.filter(Booking.prepaid_amount > 0).all()
    patched = 0

    for booking in bookings:
        active_rooms = [r for r in booking.rooms if r.status in ['booked', 'checked_in']]
        if not active_rooms:
            continue

        current_sum = sum(float(r.room_deposit_amount or 0) for r in active_rooms)
        target_sum = float(booking.prepaid_amount or 0)

        if target_sum <= 0 or abs(current_sum - target_sum) < 0.01:
            continue

        weights = [float(r.price_snapshot or 0) if float(r.price_snapshot or 0) > 0 else 1.0 for r in active_rooms]
        total_weight = sum(weights) or float(len(active_rooms))

        allocated = 0.0
        for idx, room_row in enumerate(active_rooms):
            if idx == len(active_rooms) - 1:
                share = max(0.0, round(target_sum - allocated, 2))
            else:
                share = round(target_sum * (weights[idx] / total_weight), 2)
                allocated += share
            room_row.room_deposit_amount = share
            room_row.room_deposit_original = max(float(room_row.room_deposit_original or 0), share)

        patched += 1

    if patched > 0:
        db.session.commit()
        print(f">>> Đã backfill cọc theo phòng cho {patched} booking")


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        ensure_schema_updates()
        backfill_room_deposits()
        
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