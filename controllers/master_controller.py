from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func

from decorators import master_admin_required
from extensions import db
from models import Booking, Hotel, Room, User
from services import audit_service, time_service


master_bp = Blueprint('master', __name__)


@master_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated and current_user.is_super_admin:
        return redirect(url_for('master.dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(username=(request.form.get('username') or '')).first()
        if not user or not user.is_super_admin or not user.check_password(request.form.get('password') or ''):
            flash('Master admin không hợp lệ.', 'error')
            return redirect(url_for('master.login'))
        login_user(user, remember=bool(request.form.get('remember')))
        return redirect(url_for('master.dashboard'))
    return render_template('master/login.html')


@master_bp.route('/logout')
@login_required
@master_admin_required
def logout():
    logout_user()
    return redirect(url_for('master.login'))


@master_bp.route('')
@login_required
@master_admin_required
def dashboard():
    hotels = Hotel.query.order_by(Hotel.name).all()
    room_counts = dict(db.session.query(Room.hotel_id, func.count(Room.id)).group_by(Room.hotel_id))
    user_counts = dict(db.session.query(User.hotel_id, func.count(User.id)).filter(User.hotel_id.isnot(None)).group_by(User.hotel_id))
    today_business = time_service.business_today()
    start_utc, end_utc = time_service.business_day_utc_bounds(today_business)
    metrics = {
        'total_rooms': Room.query.count(),
        'occupied_rooms': Room.query.filter_by(status='occupied').count(),
        'today_bookings': Booking.query.filter(
            Booking.created_at >= start_utc,
            Booking.created_at < end_utc,
        ).count(),
    }
    return render_template('master/dashboard.html', hotels=hotels, room_counts=room_counts, user_counts=user_counts, metrics=metrics)


@master_bp.route('/hotels')
@login_required
@master_admin_required
def hotels():
    return redirect(url_for('master.dashboard'))


@master_bp.route('/hotels/create', methods=['POST'])
@login_required
@master_admin_required
def create_hotel():
    name = (request.form.get('name') or '').strip()
    slug = (request.form.get('slug') or '').strip().lower()
    username = (request.form.get('admin_username') or '').strip()
    password = request.form.get('admin_password') or ''
    if not all([name, slug, username, password]) or Hotel.query.filter_by(slug=slug).first() or User.query.filter_by(username=username).first():
        return 'Dữ liệu khách sạn hoặc tài khoản không hợp lệ.', 400
    try:
        hotel = Hotel(name=name, slug=slug, is_active=True)
        db.session.add(hotel)
        db.session.flush()
        admin = User(username=username, role='admin', hotel_id=hotel.id, is_super_admin=False)
        admin.set_password(password)
        db.session.add(admin)
        audit_service.record_event(
            hotel_id=hotel.id,
            actor_user_id=current_user.id,
            action='create_hotel',
            entity_type='hotel',
            entity_id=hotel.id,
            after_data={
                'name': hotel.name,
                'slug': hotel.slug,
                'admin_username': admin.username,
            },
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        return 'Không thể tạo khách sạn.', 400
    return redirect(url_for('master.dashboard'))


@master_bp.route('/hotels/<int:hotel_id>/enter')
@login_required
@master_admin_required
def enter_hotel(hotel_id):
    hotel = db.session.get(Hotel, hotel_id)
    if not hotel:
        abort(404)
    return redirect(url_for('room.map_view', hotel_slug=hotel.slug))


@master_bp.route('/hotels/<int:hotel_id>/toggle-active', methods=['POST'])
@login_required
@master_admin_required
def toggle_hotel_active(hotel_id):
    hotel = db.session.get(Hotel, hotel_id)
    if not hotel:
        abort(404)
    hotel.is_active = not bool(hotel.is_active)
    db.session.commit()
    return redirect(url_for('master.dashboard'))
