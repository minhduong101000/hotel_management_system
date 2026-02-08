from flask_login import UserMixin
from werkzeug.security import check_password_hash
from extensions import db, login_manager # <--- 1. Bổ sung import login_manager

class User(UserMixin, db.Model):
    __tablename__ = 'Users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100))
    role = db.Column(db.String(20), default='staff')
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# --- 2. BỔ SUNG ĐOẠN NÀY VÀO CUỐI FILE ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))