from flask import Flask, abort, g, jsonify, redirect, render_template, request, url_for
from sqlalchemy import text as sa_text
from extensions import csrf, db, login_manager, mail
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFError
from models import User
from models.hotel import Hotel
from commands import register_commands
from config import apply_runtime_config

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
from controllers.master_controller import master_bp
from controllers.audit_controller import audit_bp
from controllers.refund_controller import refund_bp

def create_app(test_config=None, environment=None):
    app = Flask(__name__)

    # --- 1. CẤU HÌNH APP ---
    apply_runtime_config(app, environment=environment, test_config=test_config)

    # --- 2. KHỞI TẠO EXTENSIONS ---
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    Migrate(app, db)
    register_commands(app)

    # --- [QUAN TRỌNG] CẤU HÌNH LOGIN MANAGER ---
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Vui lòng đăng nhập để tiếp tục."

    @login_manager.unauthorized_handler
    def handle_unauthorized():
        # API hết phiên phải nhận JSON 401 để JS xử lý được — 302 HTML từng
        # khiến nút bấm "chết im lặng" khi session hết hạn (chính sách 14-08).
        if '/api/' in request.path or request.is_json:
            return jsonify(
                success=False,
                error_code='unauthenticated',
                msg='Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',
            ), 401
        hotel_slug = getattr(g, 'hotel_slug', None)
        if hotel_slug:
            return redirect(url_for('auth.login', hotel_slug=hotel_slug, next=request.path))
        return redirect(url_for('auth.login', hotel_slug='central', next=request.path))

    @login_manager.user_loader
    def load_user(user_uniquifier):
        return User.query.filter_by(fs_uniquifier=user_uniquifier).first()

    # --- 3. ĐĂNG KÝ BLUEPRINTS VỚI TENANT PREFIX ---
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
    app.register_blueprint(audit_bp, url_prefix=f"{tenant_prefix}/activity-log")
    app.register_blueprint(refund_bp, url_prefix=tenant_prefix)
    app.register_blueprint(master_bp, url_prefix='/master')

    # --- 4. XỬ LÝ ĐA TENANT (URL SLUG) ---
    @app.url_value_preprocessor
    def pull_hotel_slug(endpoint, values):
        if values and 'hotel_slug' in values:
            g.hotel_slug = values.pop('hotel_slug')
        elif 'hotel_slug' in g:
            pass
        else:
            pass

    @app.url_defaults
    def add_language_code(endpoint, values):
        if 'hotel_slug' in values or not getattr(g, 'hotel_slug', None):
            pass
        else:
            if app.url_map.is_endpoint_expecting(endpoint, 'hotel_slug'):
                values['hotel_slug'] = g.hotel_slug

        if endpoint == 'static':
            import time
            values['v'] = int(time.time() / 10)

    @app.context_processor
    def inject_hotel_slug():
        return dict(hotel_slug=getattr(g, 'hotel_slug', ''))

    @app.before_request
    def load_current_hotel():
        if not getattr(g, 'hotel_slug', None):
            return
            
        hotel = Hotel.query.filter_by(slug=g.hotel_slug, is_active=True).first()
        if not hotel:
            abort(404, description="Khách sạn không tồn tại hoặc đã ngừng hoạt động.")
        
        g.current_hotel = hotel
        g.hotel_id = hotel.id

        from flask_login import current_user
        if current_user.is_authenticated:
            if not current_user.is_super_admin and current_user.hotel_id != g.hotel_id:
                abort(403, description="Bạn không có quyền truy cập vào khách sạn này.")

    # --- 4b. LOGGING (INFO ra stdout — container gom qua json-file driver) ---
    if not app.config.get('TESTING'):
        import logging as _logging
        _logging.basicConfig(
            level=_logging.INFO,
            format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        )

    # --- 5. ROUTES HỆ THỐNG ---
    @app.route('/healthz')
    def healthz():
        # Route công khai cho healthcheck/uptime — không tenant, không auth.
        try:
            db.session.execute(sa_text('SELECT 1'))
        except Exception:
            return jsonify(status='degraded'), 503
        return jsonify(status='ok')

    @app.route('/')
    def index():
        return redirect(url_for('room.map_view', hotel_slug='central')) 

    @app.after_request
    def add_production_security_headers(response):
        if app.config["APP_ENV"] == "production":
            # CSP report-only khong report-to = vo dung + spam console Safari.
            # CSP that can ke hoach rieng (inline JS + CDN unpkg).
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "same-origin"
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
        return response

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        message = "Phiên thao tác không hợp lệ hoặc đã hết hạn."
        if request.is_json or "/api/" in request.path:
            return (
                jsonify(
                    success=False,
                    error_code="csrf_failed",
                    msg=message,
                ),
                400,
            )
        return render_template("errors/csrf.html", message=message), 400

    return app

app = create_app()


if __name__ == '__main__':
    if app.config["APP_ENV"] != "development":
        raise RuntimeError(
            "Entrypoint trực tiếp chỉ dành cho development; "
            "production phải chạy qua WSGI server."
        )
    app.run(debug=app.config["DEBUG"])
