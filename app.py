from flask import Flask, redirect, url_for
from flask_login import LoginManager
from config import Config
from models import db, User
from controllers.auth_controller import auth_bp
from controllers.dashboard_controller import dashboard_bp

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)

# Tool tạo User nhanh (Chạy lần đầu rồi xóa)
@app.route('/create-init-user')
def create_user():
    try:
        if not User.query.filter_by(username='admin').first():
            u = User(username='admin', full_name='Quản Lý', role='admin')
            u.set_password('123456')
            db.session.add(u)
        
        if not User.query.filter_by(username='staff').first():
            u = User(username='staff', full_name='Nhân Viên', role='staff')
            u.set_password('123456')
            db.session.add(u)
            
        db.session.commit()
        return "Đã tạo user: admin/123456 và staff/123456"
    except Exception as e: return f"Lỗi: {e}"

@app.route('/')
def root():
    return redirect(url_for('dashboard.timeline_view'))

if __name__ == '__main__':
    app.run(debug=True)