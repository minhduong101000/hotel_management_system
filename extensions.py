from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask import g
from sqlalchemy import event
from sqlalchemy.orm import Query, Session

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()

@event.listens_for(Query, "before_compile", retval=True)
def ensure_hotel_isolation(query):
    """Tự động thêm filter hotel_id vào mọi câu lệnh SQL nếu model có hotel_id."""
    # Không áp dụng nếu chưa có tenant context
    if not hasattr(g, 'hotel_id'):
        return query

    # QUAN TRỌNG: Không thể gọi filter() sau khi đã có LIMIT/OFFSET
    # (ví dụ: khi .first() gọi nội bộ .limit(1) rồi mới trigger before_compile)
    if query._limit_clause is not None or query._offset_clause is not None:
        return query

    # Duyệt qua các entities trong query
    for entity in query.column_descriptions:
        model_class = entity.get('entity')
        if model_class and hasattr(model_class, 'hotel_id'):
            query = query.filter(model_class.hotel_id == g.hotel_id)
            
    return query

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