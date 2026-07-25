from flask import abort, g

def current_hotel_id():
    hotel_id = getattr(g, "hotel_id", None)
    if hotel_id is None:
        abort(404)
    return hotel_id

def tenant_query(model):
    return model.query.filter(model.hotel_id == current_hotel_id())

def tenant_get_or_404(model, record_id):
    return tenant_query(model).filter(model.id == record_id).first_or_404()
