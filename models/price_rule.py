from extensions import db
from datetime import datetime

class PriceRule(db.Model):
    __tablename__ = 'price_rules'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    room_type = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    priority = db.Column(db.Integer, default=1)
    
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    days_of_week = db.Column(db.String(20), nullable=True) # VD: "6,7" (T7, CN)
    
    price_daily = db.Column(db.Numeric(10, 2), nullable=False)
        
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f'<PriceRule {self.name} - {self.room_type}>'