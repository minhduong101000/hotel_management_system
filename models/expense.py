from extensions import db

class Expense(db.Model):
    __tablename__ = 'expenses'

    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # Điện nước, Lương, Mua sắm, Sửa chữa, Khác
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    expense_date = db.Column(db.Date, nullable=False, default=db.func.now())
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    is_voided = db.Column(db.Boolean, nullable=False, default=False)
    void_reason = db.Column(db.String(255), nullable=True)
    voided_at = db.Column(db.DateTime, nullable=True)
    voided_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    user = db.relationship('User', foreign_keys=[created_by], backref='expenses')
    voided_user = db.relationship('User', foreign_keys=[voided_by])

    def to_dict(self):
        return {
            'id': self.id,
            'category': self.category,
            'description': self.description,
            'amount': float(self.amount or 0),
            'expense_date': self.expense_date.strftime('%Y-%m-%d') if self.expense_date else '',
            'created_by': self.user.username if self.user else 'N/A',
            'created_at': self.created_at.strftime('%H:%M %d/%m/%Y') if self.created_at else '',
            'is_voided': bool(self.is_voided),
            'void_reason': self.void_reason,
        }
