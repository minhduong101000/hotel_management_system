from flask import Flask, redirect, url_for
from extensions import db, login_manager, migrate
from werkzeug.security import generate_password_hash
from models import User

# Import các Controllers
from controllers.auth_controller import auth_bp
from controllers.billing_controller import billing_bp
from controllers.customer_controller import customer_bp
from controllers.room_controller import room_bp
from controllers.timeline_controller import timeline_bp
from controllers.service_controller import service_bp
from controllers.warehouse_controller import warehouse_bp
from controllers.staff_controller import staff_bp
from controllers.report_controller import report_bp
from controllers.setting_controller import setting_bp
from controllers.price_controller import price_bp
from controllers.booking_controller import booking_bp

from config import get_config

app = Flask(__name__)
app.config.from_object(get_config())

# 1. Init Extensions
db.init_app(app)
login_manager.init_app(app)
migrate.init_app(app, db)

# 2. Register Blueprints (Controllers)
app.register_blueprint(auth_bp)
app.register_blueprint(customer_bp)
app.register_blueprint(room_bp)
app.register_blueprint(timeline_bp)
app.register_blueprint(service_bp)
app.register_blueprint(billing_bp)
app.register_blueprint(warehouse_bp)
app.register_blueprint(staff_bp)
app.register_blueprint(report_bp)
app.register_blueprint(setting_bp)
app.register_blueprint(price_bp)
app.register_blueprint(booking_bp)


# 3. Routes mặc định
@app.route('/')
def index():
    return redirect(url_for('room.map_view')) # Chú ý: 'room.' là tên blueprint

@app.cli.command('seed-admin')
def seed_admin():
    """Tạo tài khoản admin đầu tiên từ ADMIN_USERNAME / ADMIN_PASSWORD trong env."""
    import os
    username = os.environ.get('ADMIN_USERNAME', 'admin')
    password = os.environ.get('ADMIN_PASSWORD')
    if not password:
        raise SystemExit('ADMIN_PASSWORD chưa được đặt trong env')
    with app.app_context():
        if User.query.filter_by(username=username).first():
            print(f'User "{username}" đã tồn tại — bỏ qua.')
            return
        db.session.add(User(username=username,
                            password_hash=generate_password_hash(password),
                            role='admin'))
        db.session.commit()
        print(f'Đã tạo admin "{username}".')

if __name__ == '__main__':
    app.run(debug=True)