from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask import g
from sqlalchemy import event
from sqlalchemy.orm import Query, Session

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()



@event.listens_for(Session, "before_flush")
def add_hotel_id_to_new_objects(session, flush_context, instances):
    """Tự động gắn hotel_id vào các object mới tạo."""
    if not hasattr(g, 'hotel_id'):
        return

    for obj in session.new:
        if hasattr(obj, 'hotel_id'):
            val = getattr(obj, 'hotel_id')
            if val is None:
                setattr(obj, 'hotel_id', g.hotel_id)