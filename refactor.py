import re
import glob

def refactor_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # ensure import
    if "from services.tenant_service import" not in content:
        content = "from services.tenant_service import tenant_query, tenant_get_or_404\n" + content
    
    # replace query.get_or_404
    content = re.sub(r'\b(Room|Booking|BookingRoom|Customer|Service)\.query\.get_or_404\((.*?)\)', 
                     r'tenant_get_or_404(\1, \2)', content)
    
    # replace query.get
    # .get might return None, tenant_get_or_404 aborts with 404. The plan says:
    # "Thay các Room.query.get(...), ... bằng helper hoặc tenant_query"
    # We can replace X.query.get(id) with tenant_query(X).get(id) safely? No, .get() is not available on query in SQLAlchemy 3, but in 2 it's legacy.
    # Actually, we can just replace X.query.get(id) with tenant_query(X).filter_by(id=...).first()
    # Or just replace X.query with tenant_query(X).
    content = re.sub(r'\b(Room|Booking|BookingRoom|Customer|Service)\.query\b', 
                     r'tenant_query(\1)', content)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

for controller in ['room_controller.py', 'booking_controller.py', 'timeline_controller.py']:
    refactor_file(f'controllers/{controller}')
