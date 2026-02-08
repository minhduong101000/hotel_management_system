from flask import Flask, redirect, url_for
from extensions import db, login_manager
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

app = Flask(__name__)
app.config['SECRET_KEY'] = 'luxury-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:123456@localhost/Hotel_Management_System'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 1. Init Extensions
db.init_app(app)
login_manager.init_app(app)

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

@app.route('/init-db')
def init_db():
    with app.app_context():
        db.create_all()
        # Tạo admin mặc định nếu chưa có
        if not User.query.filter_by(username='admin').first():
            u = User(username='admin', password_hash=generate_password_hash('123456'), role='admin')
            db.session.add(u)
            db.session.commit()
    return "Đã khởi tạo Database thành công!"

if __name__ == '__main__':
    app.run(debug=True)