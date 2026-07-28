from services.tenant_service import tenant_query, tenant_get_or_404
from flask import Blueprint, jsonify, request, render_template, g
from models.hotel import Hotel
from services.notification_service import send_booking_notification
from flask_login import login_required, current_user
from extensions import db
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError

# =======================================================
# IMPORT MODELS (Đúng cấu trúc)
# =======================================================
from models.room import Room
from models.service import Service
from models.booking_service import BookingService
from models.booking import Booking
from models.booking_room import BookingRoom
from models.customer import Customer
from models.business_operation import BusinessOperation

# Import Shared Logic
from services.pricing_service import calculate_complex_hotel_bill, get_effective_room_prices, get_nightly_price_breakdown
from services import inventory_service, payment_service
from services import audit_service

booking_bp = Blueprint('booking', __name__)


def _resolve_active_booking_room(room, booking_id=None, booking_room_id=None, now=None, persist_sync=False):
    """
    Tìm booking_room đang ở (checked_in).
    Nếu lệch trạng thái (room occupied nhưng booking_room còn booked), tự đồng bộ sang checked_in.
    """
    now = now or datetime.now()

    query = tenant_query(BookingRoom).filter(
        BookingRoom.room_id == room.id,
        BookingRoom.status == 'checked_in'
    )
    if booking_room_id:
        query = query.filter(BookingRoom.id == booking_room_id)
    if booking_id:
        query = query.filter(BookingRoom.booking_id == booking_id)

    booking_room = query.order_by(
        BookingRoom.check_in_actual.desc(),
        BookingRoom.check_in_expected.desc()
    ).first()

    if booking_room:
        return booking_room

    # Fallback cho dữ liệu cũ/lệch trạng thái:
    # phòng đã occupied nhưng booking_room còn booked.
    if room.status != 'occupied':
        return None

    fallback_query = tenant_query(BookingRoom).filter(
        BookingRoom.room_id == room.id,
        BookingRoom.status == 'booked',
        BookingRoom.check_in_expected <= now + timedelta(hours=6)
    )
    if booking_room_id:
        fallback_query = fallback_query.filter(BookingRoom.id == booking_room_id)
    if booking_id:
        fallback_query = fallback_query.filter(BookingRoom.booking_id == booking_id)

    booking_room = fallback_query.order_by(BookingRoom.check_in_expected.desc()).first()
    if not booking_room:
        return None

    changed = False
    if booking_room.status != 'checked_in':
        booking_room.status = 'checked_in'
        changed = True
    if booking_room.check_in_actual is None:
        booking_room.check_in_actual = booking_room.check_in_expected or now
        changed = True

    if booking_room.booking and booking_room.booking.status not in ['checked_in', 'completed', 'cancelled']:
        booking_room.booking.status = 'checked_in'
        changed = True

    if room.status != 'occupied':
        room.status = 'occupied'
        changed = True

    if changed:
        if persist_sync:
            db.session.commit()
        else:
            db.session.flush()

    return booking_room


def _is_last_active_room_for_booking(booking_id, current_booking_room_id=None):
    """
    True khi không còn phòng active nào khác trong cùng booking.
    Active = booked hoặc checked_in.
    """
    query = tenant_query(BookingRoom).filter(
        BookingRoom.booking_id == booking_id,
        BookingRoom.status.in_(['booked', 'checked_in'])
    )

    if current_booking_room_id:
        query = query.filter(BookingRoom.id != current_booking_room_id)

    return query.first() is None

# =======================================================
# 1. LẤY THÔNG TIN BOOKING SẮP TỚI (Dùng cho Timeline)
# =======================================================
@booking_bp.route('/api/bookings/upcoming/<int:room_id>')
@login_required
def get_upcoming_booking(room_id):
    booking_room = tenant_query(BookingRoom).filter(
        BookingRoom.room_id == room_id,
        BookingRoom.status == 'booked'
    ).order_by(BookingRoom.check_in_expected.asc()).first()
    
    if booking_room:
        parent_booking = booking_room.booking
        customer_name = "Khách lẻ"
        if parent_booking and parent_booking.customer:
            customer_name = parent_booking.customer.name

        return jsonify({
            'has_booking': True,
            'booking_id': parent_booking.id if parent_booking else None,
            'booking_room_id': booking_room.id,
            'customer_name': customer_name,
            'check_in_time': booking_room.check_in_expected.strftime('%H:%M %d/%m'),
            'rental_type': booking_room.rental_type
        })
    return jsonify({'has_booking': False})

# =======================================================
# 2. CHECK-IN 
# =======================================================
@booking_bp.route('/api/rooms/checkin', methods=['POST'])
@login_required
def checkin_room():
    req_data = request.get_json(silent=True) or {}
    booking_room_id = req_data.get('booking_room_id')
    if not isinstance(booking_room_id, int):
        return jsonify(success=False, msg="Thiếu booking_room_id hợp lệ."), 400

    booking_room = tenant_get_or_404(BookingRoom, booking_room_id)
    room = booking_room.room
    before_data = {'booking_status': booking_room.status, 'room_status': room.status}
    
    if booking_room.status != 'booked':
        return jsonify({'success': False, 'msg': 'Trạng thái không hợp lệ để check-in.'}), 400
        
    if room.clean_status == 'dirty': 
        return jsonify({'success': False, 'msg': 'Phòng đang bẩn, hãy dọn trước!'}), 400

    if room.status == 'occupied':
        return jsonify({'success': False, 'msg': 'Phòng đang có khách, không thể check-in thêm.'}), 400

    now = datetime.now()
    if booking_room.check_in_expected and booking_room.check_in_expected - now > timedelta(hours=3):
        return jsonify({'success': False, 'msg': 'Chỉ được check-in sớm tối đa 3 giờ trước giờ booking.'}), 400

    booking_room.status = 'checked_in'
    booking_room.check_in_actual = now
    room.status = 'occupied'
    
    if booking_room.booking:
         booking_room.booking.status = 'checked_in'

    audit_service.record_event(
        hotel_id=booking_room.hotel_id,
        actor_user_id=current_user.id,
        action='checkin',
        entity_type='booking_room',
        entity_id=booking_room.id,
        before_data=before_data,
        after_data={
            'booking_status': booking_room.status,
            'room_status': room.status,
            'check_in_actual': booking_room.check_in_actual.isoformat(),
        },
    )

    db.session.commit()
    
    customer_name = booking_room.booking.customer.name if (booking_room.booking and booking_room.booking.customer) else "Khách"
    return jsonify({'success': True, 'booking_room_id': booking_room.id, 'msg': f'Check-in thành công cho {customer_name}'})

# =======================================================
# 3. IN HÓA ĐƠN ĐẶT CỌC
# =======================================================
@booking_bp.route('/api/bookings/<int:booking_id>/deposit-invoice', methods=['GET'])
@login_required
def print_deposit_invoice(booking_id):
    booking = tenant_query(Booking).filter_by(id=booking_id).first()
    if not booking:
        return jsonify({'success': False, 'msg': 'Không tìm thấy thông tin đặt phòng.'}), 404

    customer_name = booking.customer.name if booking.customer else "Khách lẻ"
    customer_phone = booking.customer.phone if booking.customer else "--"
    customer_email = booking.customer.email if (booking.customer and booking.customer.email) else "--"
    deposit_date = booking.created_at.strftime('%d/%m/%Y %H:%M') if booking.created_at else datetime.now().strftime('%d/%m/%Y %H:%M')
    deposit_amount = float(booking.prepaid_amount or 0)
    room_number = ", ".join([br.room.room_number for br in booking.rooms if br.room]) or "--"

    invoice_lines = []
    estimated_total = 0.0
    for idx, br in enumerate(booking.rooms, start=1):
        room_label = br.room.room_number if br.room else f"P{idx}"
        rental_type_map = {'daily': 'Ngay', 'hourly': 'Gio'}
        rental_type_label = rental_type_map.get(br.rental_type, br.rental_type or '--')

        checkin_txt = br.check_in_expected.strftime('%d/%m/%Y %H:%M') if br.check_in_expected else '--'
        checkout_txt = br.check_out_expected.strftime('%d/%m/%Y %H:%M') if br.check_out_expected else '--'

        unit_price = float(br.price_snapshot or 0)
        estimated_total += unit_price

        invoice_lines.append({
            'room_label': room_label,
            'rental_type': rental_type_label,
            'period_text': f"{checkin_txt} - {checkout_txt}",
            'qty': 1,
            'unit_price': unit_price,
            'line_total': unit_price
        })

    remaining_amount = max(0.0, estimated_total - deposit_amount)

    return render_template('billing/deposit_invoice.html', 
                           booking_code=booking.code,
                           customer_name=customer_name, 
                           customer_phone=customer_phone,
                           customer_email=customer_email,
                           deposit_date=deposit_date, 
                           deposit_amount=deposit_amount, 
                           room_number=room_number,
                           invoice_lines=invoice_lines,
                           estimated_total=estimated_total,
                           remaining_amount=remaining_amount)

# =======================================================
# 4. CẬP NHẬT SỐ LƯỢNG DỊCH VỤ (+/-)
# =======================================================
@booking_bp.route('/api/bookings/update_service_quantity', methods=['POST'])
@login_required
def update_service_quantity():
    try:
        data = request.json
        booking_id = data.get('booking_id')
        service_id = data.get('service_id')
        room_id = data.get('room_id')
        change = int(data.get('change', 0))

        if not booking_id or not service_id:
            return jsonify({'success': False, 'msg': 'Thiếu thông tin.'})

        filter_kwargs = {'booking_id': booking_id, 'service_id': service_id}
        if room_id:
            filter_kwargs['room_id'] = room_id
        line_item = tenant_query(BookingService).filter_by(**filter_kwargs).first()

        if not line_item:
            return jsonify({'success': False, 'msg': 'Không tìm thấy dịch vụ trên hóa đơn.'}), 404

        current_quantity = int(line_item.quantity or 0)
        new_quantity = max(0, current_quantity + change)
        applied_change = new_quantity - current_quantity
        before_data = {
            'service_id': line_item.service_id,
            'room_id': line_item.room_id,
            'quantity': current_quantity,
            'price_at_booking': float(line_item.price_at_booking or 0),
        }

        if applied_change > 0:
            inventory_service.validate_inventory(line_item.hotel_id, {
                int(service_id): applied_change
            })
            inventory_service.deduct_inventory(
                line_item.hotel_id, int(service_id), applied_change
            )
        elif applied_change < 0:
            inventory_service.restore_inventory(
                line_item.hotel_id, int(service_id), -applied_change
            )

        if new_quantity == 0:
            db.session.delete(line_item)
        else:
            line_item.quantity = new_quantity

        audit_service.record_event(
            hotel_id=line_item.hotel_id,
            actor_user_id=current_user.id,
            action='update_booking_service_quantity',
            entity_type='booking_service',
            entity_id=line_item.id,
            before_data=before_data,
            after_data={
                'service_id': line_item.service_id,
                'room_id': line_item.room_id,
                'quantity': new_quantity,
                'price_at_booking': float(line_item.price_at_booking or 0),
            },
        )

        db.session.commit()
        return jsonify({'success': True})

    except inventory_service.InsufficientInventoryError as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(e)}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(e)})

# =======================================================
# 5. PREVIEW HÓA ĐƠN TRẢ PHÒNG
# =======================================================
@booking_bp.route('/api/rooms/preview_checkout', methods=['POST'])
@login_required
def preview_checkout_room():
    data = request.get_json() or {}
    room_number = data.get('number')
    booking_id = data.get('booking_id')
    include_tax_raw = data.get('include_tax', False)
    include_tax = str(include_tax_raw).strip().lower() in ['1', 'true', 'yes', 'on']

    if not room_number:
        return jsonify({'success': False, 'msg': 'Thiếu số phòng.'})

    room = tenant_query(Room).filter(Room.room_number == room_number).first()
    if not room:
        return jsonify({'success': False, 'msg': 'Phòng không tồn tại.'})

    now = datetime.now()
    booking_room = _resolve_active_booking_room(
        room=room,
        booking_id=booking_id,
        now=now,
        persist_sync=True
    )

    if not booking_room:
        return jsonify({'success': False, 'msg': 'Không tìm thấy phòng đang check-in để thanh toán.'})

    check_in_time = booking_room.check_in_actual or booking_room.check_in_expected or datetime.now()
    check_out_time = datetime.now()

    room_fee, breakdown = calculate_complex_hotel_bill(
        check_in_time,
        check_out_time,
        room,
        rental_type=booking_room.rental_type,
        expected_check_in=booking_room.check_in_expected,
        expected_check_out=booking_room.check_out_expected,
        price_breakdown_snapshot=booking_room.price_breakdown_snapshot
    )

    room_services = tenant_query(BookingService).filter_by(
        booking_id=booking_room.booking_id,
        room_id=room.id
    ).all()

    services_data = []
    service_fee = 0.0
    for item in room_services:
        price = float(item.price_at_booking or (item.service.price if item.service else 0))
        qty = int(item.quantity or 0)
        total = price * qty
        service_fee += total
        services_data.append({
            'service_id': item.service_id,
            'name': item.service.name if item.service else 'Dich vu',
            'quantity': qty,
            'price': price,
            'total': total
        })

    total_before_tax = float(room_fee) + float(service_fee)
    tax_rate = 0.08
    tax_amount = round(total_before_tax * tax_rate, 2) if include_tax else 0.0
    total_bill = total_before_tax + tax_amount

    prepaid_amount = 0.0
    apply_deposit_now = False
    if booking_room.booking:
        apply_deposit_now = _is_last_active_room_for_booking(
            booking_id=booking_room.booking.id,
            current_booking_room_id=booking_room.id
        )
        if apply_deposit_now:
            prepaid_amount = float(booking_room.booking.prepaid_amount or 0)

    final_amount = total_bill - prepaid_amount

    def _format_vnd(amount):
        return f"{int(round(amount)):,.0f}".replace(',', '.')

    customer_name = 'Khách lẻ'
    if booking_room.booking and booking_room.booking.customer:
        customer_name = booking_room.booking.customer.name

    if booking_room.rental_type == 'daily':
        rental_type_text = 'Theo ngày'
    elif booking_room.rental_type == 'hourly':
        rental_type_text = 'Theo giờ'
    else:
        rental_type_text = booking_room.rental_type or '--'

    duration_msg = breakdown[0]['detail'] if breakdown else ''

    return jsonify({
        'success': True,
        'booking_id': booking_room.booking_id,
        'booking_room_id': booking_room.id,
        'room_number': room.room_number,
        'customer_name': customer_name,
        'check_in': check_in_time.strftime('%H:%M %d/%m/%Y'),
        'check_out': check_out_time.strftime('%H:%M %d/%m/%Y'),
        'rental_type': rental_type_text,
        'bill_details': breakdown,
        'duration_msg': duration_msg,
        'services': services_data,
        'formatted_room_fee': _format_vnd(room_fee),
        'formatted_service_fee': _format_vnd(service_fee),
        'include_tax': include_tax,
        'tax_rate': int(tax_rate * 100),
        'tax_amount': tax_amount,
        'formatted_tax_amount': _format_vnd(tax_amount),
        'formatted_total_bill': _format_vnd(total_bill),
        'apply_deposit_now': apply_deposit_now,
        'prepaid_amount': prepaid_amount,
        'formatted_prepaid_amount': _format_vnd(prepaid_amount),
        'final_amount': final_amount,
        'formatted_final_amount': f"{_format_vnd(final_amount)} đ"
    })

# =======================================================
# 6. XÁC NHẬN TRẢ PHÒNG (CHECKOUT CONFIRM)
# =======================================================
@booking_bp.route('/api/rooms/checkout', methods=['POST'])
@login_required
def checkout_room():
    data = request.get_json() or {}
    room_number = data.get('number')
    booking_room_id = data.get('booking_room_id')
    booking_id = data.get('booking_id')
    amount_raw = data.get('amount', '0')
    include_tax_raw = data.get('include_tax', False)
    include_tax = str(include_tax_raw).strip().lower() in ['1', 'true', 'yes', 'on']

    def _parse_amount(raw):
        if raw is None:
            return 0.0
        if isinstance(raw, (int, float)):
            return float(raw)

        s = str(raw).strip().replace('đ', '').replace('VND', '').replace(' ', '')

        if s.count('.') > 1 and s.count(',') == 0:
            s = s.replace('.', '')
        if s.count(',') > 1 and s.count('.') == 0:
            s = s.replace(',', '')

        if ',' in s and '.' in s:
            if s.rfind(',') > s.rfind('.'):
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '')
        elif ',' in s:
            s = s.replace(',', '.')

        try:
            return float(s)
        except ValueError:
            return 0.0

    payment_received = _parse_amount(amount_raw)

    room = tenant_query(Room).filter(Room.room_number == room_number).first()
    if not room:
         return jsonify({'success': False, 'msg': 'Phòng không tồn tại.'})

    if booking_room_id:
        completed_booking_room = tenant_query(BookingRoom).filter_by(
            id=booking_room_id,
            room_id=room.id,
            status='checked_out',
        ).first()
        if completed_booking_room:
            return jsonify({
                'success': False,
                'msg': 'Phòng này đã checkout.',
                'operation_key': f'checkout:{completed_booking_room.id}',
            }), 409

    now = datetime.now()
    booking_room = _resolve_active_booking_room(
        room=room,
        booking_id=booking_id,
        booking_room_id=booking_room_id,
        now=now,
        persist_sync=False
    )

    if booking_room:
        operation_key = f'checkout:{booking_room.id}'
        existing_operation = tenant_query(BusinessOperation).filter_by(
            operation_key=operation_key
        ).first()
        if existing_operation:
            return jsonify({
                'success': False,
                'msg': 'Phòng này đã checkout.',
                'operation_key': operation_key,
            }), 409

        operation = BusinessOperation(
            hotel_id=room.hotel_id,
            operation_key=operation_key,
            action='checkout',
            entity_type='booking_room',
            entity_id=booking_room.id,
        )
        db.session.add(operation)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            return jsonify({
                'success': False,
                'msg': 'Phòng này đang được checkout bởi thao tác khác.',
                'operation_key': operation_key,
            }), 409

        # Nếu rơi vào fallback booked -> ghi nhận thời điểm vào ở thực tế để tính bill đúng.
        if booking_room.status == 'booked' and booking_room.check_in_actual is None:
            booking_room.check_in_actual = booking_room.check_in_expected or now

        # --- BƯỚC 1: TÍNH TOÀN BỘ TIỀN PHÒNG + DỊCH VỤ THỰC TẾ ---
        # 1. Tiền phòng
        room_fee, _ = calculate_complex_hotel_bill(
            booking_room.check_in_actual or booking_room.check_in_expected or now, 
            now, 
            room, 
            rental_type=booking_room.rental_type,
            expected_check_in=booking_room.check_in_expected,
            expected_check_out=booking_room.check_out_expected,
            price_breakdown_snapshot=booking_room.price_breakdown_snapshot
        )
        
        # 2. Tiền dịch vụ
        service_fee = 0.0
        room_services = tenant_query(BookingService).filter_by(booking_id=booking_room.booking_id, room_id=room.id).all()
        for item in room_services:
            if item.service:
                service_fee += item.quantity * float(item.price_at_booking or item.service.price)
        
        tax_rate = 0.08
        tax_amount = round((room_fee + service_fee) * tax_rate, 2) if include_tax else 0.0
        total_bill_with_tax = room_fee + service_fee + tax_amount

        # --- BƯỚC 2: CẬP NHẬT DỮ LIỆU PHÒNG ---
        booking_room.status = 'checked_out'
        booking_room.check_out_actual = now
        booking_room.final_amount = total_bill_with_tax # LƯU TỔNG CỘNG, không phải số tiền thực nhận
        
        room.status = 'available'
        room.clean_status = 'dirty'

        booking = tenant_query(Booking).filter_by(id=booking_room.booking_id).first()
        if booking:
            total_bill_nom = total_bill_with_tax
            apply_deposit_now = _is_last_active_room_for_booking(
                booking_id=booking.id,
                current_booking_room_id=booking_room.id
            )

            # --- GHI NHẬN DOANH THU VÀO SỔ QUỸ (CASHIER) ---
            # Tỷ lệ: Nếu payment_received < tổng bill (do trừ cọc), chia tỷ lệ tương đối.
            if total_bill_nom > 0 and payment_received > 0:
                ratio_room = room_fee / total_bill_nom
                ratio_service = service_fee / total_bill_nom
                ratio_tax = tax_amount / total_bill_nom

                actual_room_payment = payment_received * ratio_room
                actual_service_payment = payment_received * ratio_service
                actual_tax_payment = payment_received * ratio_tax

                distributed_total = actual_room_payment + actual_service_payment + actual_tax_payment
                rounding_gap = payment_received - distributed_total
                if rounding_gap != 0:
                    actual_room_payment += rounding_gap
            else:
                actual_room_payment = payment_received
                actual_service_payment = 0
                actual_tax_payment = 0
                
            if actual_room_payment != 0:
                payment_service.record_room_payment(
                    booking_id=booking.id,
                    amount=actual_room_payment,
                    payment_method='cash',
                    payment_type='room_payment',
                    note=f"Thanh toán tiền phòng {room.room_number}",
                    created_at=now,
                )
                
            if actual_service_payment > 0:
                payment_service.record_room_payment(
                    booking_id=booking.id,
                    amount=actual_service_payment,
                    payment_method='cash',
                    payment_type='service_payment',
                    note=f"Thanh toán tiền dịch vụ phòng {room.room_number}",
                    created_at=now,
                )

            if actual_tax_payment > 0:
                payment_service.record_room_payment(
                    booking_id=booking.id,
                    amount=actual_tax_payment,
                    payment_method='cash',
                    payment_type='tax_payment',
                    note=f"Thuế VAT 8% phòng {room.room_number}",
                    created_at=now,
                )

            # --- KIỂM TRA ĐƠN TỔNG ---
            all_rooms = tenant_query(BookingRoom).filter_by(booking_id=booking.id).all()

            # Chỉ trừ cọc khi checkout phòng cuối cùng trong booking lẻ.
            if apply_deposit_now:
                booking.prepaid_amount = 0.0
                for r in all_rooms:
                    r.room_deposit_amount = 0.0
            else:
                booking.prepaid_amount = float(booking.prepaid_amount or 0)
            
            # CẬP NHẬT TỔNG TIỀN ĐƠN (Dùng để hiển thị trong Hóa đơn cũ - cập nhật liên tục)
            booking.total_amount = sum(float(r.final_amount or 0) for r in all_rooms)
            booking.updated_at = now # Cưỡng bức cập nhật thời gian
            
            if all(r.status in ['checked_out', 'cancelled'] for r in all_rooms):
                booking.status = 'completed'

        operation.status = 'completed'
        operation.completed_at = now
        audit_service.record_event(
            hotel_id=room.hotel_id,
            actor_user_id=current_user.id,
            action='checkout',
            entity_type='booking_room',
            entity_id=booking_room.id,
            operation_key=operation_key,
            before_data={'status': 'checked_in'},
            after_data={'status': 'checked_out', 'final_amount': float(total_bill_with_tax)},
        )
        db.session.commit()
        return jsonify({
            'success': True,
            'msg': f'Trả phòng {room_number} thành công!',
            'operation_key': operation_key,
        })
        
    return jsonify({'success': False, 'msg': 'Không tìm thấy đơn để thanh toán.'})

# =======================================================
# 6. THÊM ORDER DỊCH VỤ
# =======================================================
@booking_bp.route('/api/bookings/orders/room/<string:room_number>', methods=['GET'])
@login_required
def order_history(room_number):
    room = tenant_query(Room).filter_by(room_number=room_number).first()
    if not room:
        return jsonify({'msg': 'Không tìm thấy phòng.'}), 404

    booking_room = tenant_query(BookingRoom).filter_by(room_id=room.id, status='checked_in').first()
    if not booking_room:
        return jsonify({'msg': 'Phòng chưa check-in.'}), 404

    line_items = tenant_query(BookingService).filter_by(
        booking_id=booking_room.booking_id,
        room_id=room.id,
    ).all()
    items = [
        {
            'service_name': item.service.name if item.service else 'Dịch vụ',
            'quantity': int(item.quantity or 0),
            'price': float(item.price_at_booking or 0),
            'total': float(item.price_at_booking or 0) * int(item.quantity or 0),
        }
        for item in line_items
    ]
    return jsonify({'items': items, 'total': sum(item['total'] for item in items)})


@booking_bp.route('/api/orders/add', methods=['POST'])
@login_required
def add_order():
    try:
        data = request.get_json(silent=True) or {}
        room_number = data.get('room_number')
        items = data.get('items')

        if not isinstance(items, list) or not items:
            return jsonify({'success': False, 'msg': 'Cần chọn ít nhất một dịch vụ.'}), 400

        room = tenant_query(Room).filter_by(room_number=room_number).first()
        if not room: return jsonify({'success': False, 'msg': 'Phòng lỗi.'})

        br = tenant_query(BookingRoom).filter_by(room_id=room.id, status='checked_in').first()
        if not br: return jsonify({'success': False, 'msg': 'Phòng chưa check-in.'})

        booking_id = br.booking_id

        validated_items = []
        for item in items:
            if not isinstance(item, dict):
                return jsonify({'success': False, 'msg': 'Dữ liệu dịch vụ không hợp lệ.'}), 400
            try:
                s_id = int(item['id'])
                qty = int(item['qty'])
            except (KeyError, TypeError, ValueError):
                return jsonify({'success': False, 'msg': 'Dữ liệu dịch vụ không hợp lệ.'}), 400

            if qty <= 0:
                return jsonify({'success': False, 'msg': 'Số lượng dịch vụ phải lớn hơn 0.'}), 400

            svc = tenant_query(Service).filter_by(id=s_id).first()
            if not svc:
                return jsonify({'success': False, 'msg': 'Dịch vụ không thuộc khách sạn hiện tại.'}), 404
            validated_items.append((s_id, qty, svc))

        requirements = inventory_service.aggregate_quantities(
            (service_id, quantity) for service_id, quantity, _ in validated_items
        )
        inventory_service.validate_inventory(room.hotel_id, requirements)

        for s_id, qty, svc in validated_items:
            
            existing = tenant_query(BookingService).filter_by(
                booking_id=booking_id, 
                service_id=s_id,
                room_id=room.id  
            ).first()

            if existing:
                existing.quantity += qty
            else:
                new_bs = BookingService(
                    hotel_id=room.hotel_id,
                    booking_id=booking_id,
                    room_id=room.id,
                    service_id=s_id,
                    quantity=qty,
                    price_at_booking=svc.price
                )
                db.session.add(new_bs)

            inventory_service.deduct_inventory(room.hotel_id, s_id, qty)

        audit_service.record_event(
            hotel_id=room.hotel_id,
            actor_user_id=current_user.id,
            action='add_booking_order',
            entity_type='booking_room',
            entity_id=br.id,
            after_data={
                'items': [
                    {
                        'service_id': service_id,
                        'quantity': quantity,
                        'unit_price': float(service.price or 0),
                    }
                    for service_id, quantity, service in validated_items
                ],
            },
        )
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Đã thêm dịch vụ và cập nhật tồn kho.'})
    except inventory_service.InsufficientInventoryError as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(e)}), 409
    except Exception as e:
        db.session.rollback()
        print(f"Lỗi thêm dịch vụ: {e}")
        return jsonify({'success': False, 'msg': str(e)})

# =======================================================
# 7. TẠO BOOKING (Đoàn/Lẻ) - BỎ CHIA CỌC, GIỮ NGUYÊN CỤC
# =======================================================
@booking_bp.route('/api/bookings/group_create', methods=['POST'])
@login_required
def create_group_booking():
    try:
        data = request.json
        customer_info = data.get('customer', {})
        room_ids = [int(rid) for rid in data.get('room_ids', [])]
        check_in_str = data.get('check_in')
        check_out_str = data.get('check_out')
        total_deposit = float(data.get('deposit', 0))
        note = data.get('note', '')

        if not room_ids or not customer_info.get('phone'):
            return jsonify({'success': False, 'msg': 'Thiếu thông tin phòng hoặc khách hàng!'})

        # Chặn payload chọn trùng phòng (frontend có thể gửi id bị lặp do thao tác nhanh).
        if len(set(room_ids)) != len(room_ids):
            return jsonify({'success': False, 'msg': 'Danh sách phòng bị trùng. Vui lòng bỏ chọn phòng trùng và thử lại.'})

        try:
            c_in_date = datetime.strptime(check_in_str[0:10], '%Y-%m-%d')
            c_out_date = datetime.strptime(check_out_str[0:10], '%Y-%m-%d')
            check_in = c_in_date.replace(hour=14, minute=0, second=0)
            check_out = c_out_date.replace(hour=12, minute=0, second=0)
        except ValueError:
             return jsonify({'success': False, 'msg': 'Lỗi định dạng ngày!'})

        if check_in >= check_out:
            return jsonify({'success': False, 'msg': 'Ngày trả phải sau ngày nhận phòng.'})

        # Lock all selected rooms in a stable order before checking availability.
        rooms_query = tenant_query(Room).filter(Room.id.in_(room_ids)).order_by(Room.id.asc()).with_for_update().all()
        room_dict = {r.id: r for r in rooms_query}

        nights = (check_out.date() - check_in.date()).days
        if nights < 1:
            nights = 1

        estimated_total = 0.0
        for room_obj in rooms_query:
            prices = get_effective_room_prices(room_obj, check_in)
            estimated_total += float(prices['p_night']) * nights

        if estimated_total <= 0:
            return jsonify({'success': False, 'msg': 'Không thể tính tổng tiền dự kiến để kiểm tra tiền cọc.'})

        expected_50 = round(estimated_total * 0.5, 2)
        expected_100 = round(estimated_total, 2)
        dep = round(total_deposit, 2)
        if not (abs(dep - expected_50) <= 1 or abs(dep - expected_100) <= 1):
            return jsonify({'success': False, 'msg': 'Tiền cọc bắt buộc phải đúng 50% hoặc 100% tổng tiền phòng dự kiến của đoàn.'})

        cccd = str(customer_info.get('cccd', '')).strip() or None
        address = str(customer_info.get('address', '')).strip() or None
        
        customer = tenant_query(Customer).filter_by(phone=customer_info['phone']).first()
        if not customer:
            customer = Customer(name=customer_info['name'], phone=customer_info['phone'], cccd=cccd, address=address)
            db.session.add(customer)
            db.session.flush()
        else:
            if cccd and not customer.cccd: customer.cccd = cccd
            if address and not customer.address: customer.address = address
            if customer_info.get('name') and customer.name in ["", "Khách lẻ"]: customer.name = customer_info.get('name')
            db.session.flush()

        time_prefix = datetime.now().strftime('%y%m%d-%H%M%S')
        booking_code = f"GRP-{time_prefix}" 

        new_booking = Booking(
            code=booking_code,           
            customer_id=customer.id,
            created_at=datetime.now(),
            status='confirmed',          
            prepaid_amount=total_deposit,
            note=f"{note} (Đoàn: {len(room_ids)} phòng)",
        )
        db.session.add(new_booking)
        db.session.flush() 

        # --- GHI NHẬN TIỀN CỌC VÀO SỔ QUỸ (CASHIER) ---
        if total_deposit > 0:
            payment_service.record_deposit(
                booking_id=new_booking.id,
                amount=total_deposit,
                payment_method='cash',
                note=f"Nhận cọc đặt đoàn {booking_code} ({len(room_ids)} phòng)",
                created_at=datetime.now(),
                flush=True,
            )

        success_count = 0
        errors = []
        created_rooms = []

        for r_id in room_ids:
            current_room = room_dict.get(r_id)
            if not current_room:
                errors.append(f"Phòng {r_id} không tồn tại.")
                continue

            if current_room.status == 'maintenance':
                errors.append(f"Phòng {current_room.room_number} đang bảo trì.")
                continue

            is_taken = tenant_query(BookingRoom).filter(
                BookingRoom.room_id == r_id,
                BookingRoom.status.in_(['booked', 'checked_in']),
                BookingRoom.check_in_expected < check_out,
                BookingRoom.check_out_expected > check_in
            ).first()

            if is_taken:
                errors.append(f"Phòng {current_room.room_number} đã có lịch.")
                continue

            room_price = float(current_room.price_per_night) if current_room else 0

            new_br = BookingRoom(
                booking_id=new_booking.id,
                room_id=r_id,
                check_in_expected=check_in,
                check_out_expected=check_out,
                status='booked',
                rental_type='daily',
                price_snapshot=room_price,
                room_deposit_amount=0
            )
            new_br.price_breakdown_snapshot = [
                {'business_date': line['business_date'].isoformat(), 'amount': float(line['amount'])}
                for line in get_nightly_price_breakdown(current_room, check_in, check_out)
            ]
            db.session.add(new_br)
            created_rooms.append(new_br)
            success_count += 1

        if success_count > 0:
            estimated_total_success = 0.0
            for br in created_rooms:
                room_obj = room_dict.get(br.room_id)
                if not room_obj:
                    continue
                prices = get_effective_room_prices(room_obj, check_in)
                estimated_total_success += float(prices['p_night']) * nights

            expected_50_success = round(estimated_total_success * 0.5, 2)
            expected_100_success = round(estimated_total_success, 2)
            dep_success = round(total_deposit, 2)
            if not (abs(dep_success - expected_50_success) <= 1 or abs(dep_success - expected_100_success) <= 1):
                db.session.rollback()
                return jsonify({'success': False, 'msg': 'Sau khi lọc phòng khả dụng, tiền cọc không còn đúng 50%/100%. Vui lòng chọn lại phòng và bấm cọc lại.'})

            if total_deposit > 0 and created_rooms:
                weights = [float(r.price_snapshot or 0) if float(r.price_snapshot or 0) > 0 else 1.0 for r in created_rooms]
                total_weight = sum(weights) or float(len(created_rooms))
                allocated = 0.0

                for idx, br in enumerate(created_rooms):
                    if idx == len(created_rooms) - 1:
                        share = max(0.0, round(total_deposit - allocated, 2))
                    else:
                        share = round(total_deposit * (weights[idx] / total_weight), 2)
                        allocated += share
                    br.room_deposit_amount = share
                    br.room_deposit_original = share

            db.session.commit()

            # --- GỬI EMAIL THÔNG BÁO CHO CHỦ KHÁCH SẠN ---
            try:
                hotel = db.session.get(Hotel, g.hotel_id)
                if hotel:
                    send_booking_notification(new_booking, hotel)
            except Exception as mail_err:
                print(f"Error triggering email notification: {mail_err}")

            msg = f"Đã đặt {success_count} phòng thành công."
            if errors:
                msg += f" (Bỏ qua {len(errors)} phòng do trùng lịch)."
            return jsonify({'success': True, 'msg': msg})
        else:
            db.session.rollback()
            return jsonify({'success': False, 'msg': 'Không đặt được phòng nào (trùng lịch hết)!'})

    except Exception as e:
        db.session.rollback()
        print(f"Lỗi Booking: {e}")
        return jsonify({'success': False, 'msg': 'Lỗi hệ thống: ' + str(e)})
    
# =======================================================
# 8. UPDATE SERVICES (Trước checkout)
# =======================================================
@booking_bp.route('/api/bookings/update_services', methods=['POST'])
@login_required
def update_services_before_checkout():
    data = request.get_json()
    room_number = data.get('number')
    new_services = data.get('services', [])

    room = tenant_query(Room).filter(Room.room_number == room_number).first()
    if not room: return jsonify({'success': False, 'msg': 'Lỗi phòng.'})

    booking_room = tenant_query(BookingRoom).filter_by(room_id=room.id, status='checked_in').first()
    if not booking_room: return jsonify({'success': False, 'msg': 'Phòng chưa checkin.'})
    
    booking = booking_room.booking

    try:
        normalized_services = []
        for item in new_services:
            service_id = int(item['service_id'])
            quantity = int(item['quantity'])
            if quantity <= 0:
                continue
            service_obj = tenant_query(Service).filter_by(id=service_id).first()
            if not service_obj:
                return jsonify({'success': False, 'msg': 'Dịch vụ không thuộc khách sạn hiện tại.'}), 404
            normalized_services.append((service_id, quantity, service_obj))

        old_items = tenant_query(BookingService).filter_by(
            booking_id=booking.id,
            room_id=room.id,
        ).all()
        old_totals = inventory_service.aggregate_quantities(
            (item.service_id, item.quantity) for item in old_items
        )
        new_totals = inventory_service.aggregate_quantities(
            (service_id, quantity) for service_id, quantity, _ in normalized_services
        )
        all_service_ids = set(old_totals) | set(new_totals)
        positive_deltas = {
            service_id: max(0, new_totals.get(service_id, 0) - old_totals.get(service_id, 0))
            for service_id in all_service_ids
        }
        inventory_service.validate_inventory(room.hotel_id, positive_deltas)

        # Thay danh sách dịch vụ trên hóa đơn sau khi đã xác thực đủ tồn kho.
        tenant_query(BookingService).filter_by(booking_id=booking.id, room_id=room.id).delete()

        for service_id, quantity, service_obj in normalized_services:
            db.session.add(BookingService(
                hotel_id=room.hotel_id,
                booking_id=booking.id,
                room_id=room.id,
                service_id=service_id,
                quantity=quantity,
                price_at_booking=service_obj.price,
            ))

        for service_id in all_service_ids:
            delta = new_totals.get(service_id, 0) - old_totals.get(service_id, 0)
            if delta > 0:
                inventory_service.deduct_inventory(room.hotel_id, service_id, delta)
            elif delta < 0:
                inventory_service.restore_inventory(room.hotel_id, service_id, -delta)
        
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Đã cập nhật dịch vụ và tồn kho.'})

    except inventory_service.InsufficientInventoryError as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(e)}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(e)})


# =======================================================
# 9. LẤY THÔNG TIN HÓA ĐƠN ĐOÀN (MỚI THÊM)
# =======================================================
@booking_bp.route('/api/bookings/<int:booking_id>/group_billing', methods=['GET'])
@login_required
def get_group_billing(booking_id):
    try:
        include_tax_raw = request.args.get('include_tax', 'false')
        include_tax = str(include_tax_raw).strip().lower() in ['1', 'true', 'yes', 'on']
        tax_rate = 0.08

        booking = tenant_get_or_404(Booking, booking_id)

        all_rooms = tenant_query(BookingRoom).filter(
            BookingRoom.booking_id == booking_id
        ).order_by(BookingRoom.id.asc()).all()

        active_rooms = [r for r in all_rooms if r.status in ['booked', 'checked_in']]
        if not all_rooms:
            return jsonify({'success': False, 'msg': 'Booking này chưa có phòng nào.'})

        room_details = []
        total_room_fee_all = 0
        total_service_fee_all = 0
        full_total_all_rooms = 0

        all_booking_services = tenant_query(BookingService).filter_by(booking_id=booking.id).all()

        services_by_room = {}
        service_summary_map = {}
        for svc in all_booking_services:
            price = float(svc.price_at_booking or (svc.service.price if svc.service else 0))
            qty = int(svc.quantity or 0)
            total = price * qty
            name = svc.service.name if svc.service else f"DV#{svc.service_id}"

            room_key = svc.room_id
            if room_key not in services_by_room:
                services_by_room[room_key] = []
            services_by_room[room_key].append({
                'service_id': svc.service_id,
                'name': name,
                'quantity': qty,
                'price': price,
                'total': total
            })

            sum_key = svc.service_id
            if sum_key not in service_summary_map:
                service_summary_map[sum_key] = {
                    'service_id': svc.service_id,
                    'name': name,
                    'quantity': 0,
                    'total': 0.0
                }
            service_summary_map[sum_key]['quantity'] += qty
            service_summary_map[sum_key]['total'] += total

        for br in all_rooms:
            include_in_settlement = br.status in ['booked', 'checked_in']
            room_services = services_by_room.get(br.room_id, [])
            service_fee = sum(float(x['total']) for x in room_services)

            if include_in_settlement:
                check_in = br.check_in_actual if br.check_in_actual else br.check_in_expected
                check_out = datetime.now()

                room_fee, breakdown = calculate_complex_hotel_bill(
                    check_in=check_in,
                    check_out=check_out,
                    room=br.room,
                    rental_type=br.rental_type,
                    expected_check_in=br.check_in_expected,
                    expected_check_out=br.check_out_expected,
                    price_breakdown_snapshot=br.price_breakdown_snapshot
                )
                subtotal = room_fee + service_fee
                total_room_fee_all += room_fee
                total_service_fee_all += service_fee
            else:
                breakdown = []
                if br.final_amount is not None:
                    subtotal = float(br.final_amount)
                    room_fee = max(0.0, subtotal - service_fee)
                else:
                    room_fee = 0.0
                    subtotal = service_fee

            full_total_all_rooms += subtotal

            status_label_map = {
                'booked': 'Đã đặt',
                'checked_in': 'Đang ở',
                'checked_out': 'Đã trả',
                'cancelled': 'Đã hủy'
            }

            room_details.append({
                'room_id': br.room_id,
                'room_name': br.room.room_number if br.room else f"Phòng {br.room_id}",
                'status': br.status,
                'status_label': status_label_map.get(br.status, br.status or '--'),
                'include_in_settlement': include_in_settlement,
                'room_fee': room_fee,
                'service_fee': service_fee,
                'subtotal': subtotal,
                'service_items': room_services,
                'breakdown': breakdown  # Bao gồm chi tiết phụ thu sớm/muộn
            })

        grand_total = total_room_fee_all + total_service_fee_all
        tax_amount = round(grand_total * tax_rate, 2) if include_tax else 0.0
        deposit = float(booking.prepaid_amount or 0)
        final_total = (grand_total + tax_amount) - deposit

        customer_phone = booking.customer.phone if booking.customer and booking.customer.phone else '--'
        created_at_text = booking.created_at.strftime('%H:%M %d/%m/%Y') if booking.created_at else '--'

        return jsonify({
            'success': True,
            'data': {
                'booking_code': booking.code,
                'customer_name': booking.customer.name if booking.customer else 'Khách đoàn',
                'customer_phone': customer_phone,
                'booking_note': booking.note or '',
                'booking_status': booking.status,
                'created_at': created_at_text,
                'rooms': room_details,
                'service_summary': list(service_summary_map.values()),
                'total_room_fee': total_room_fee_all,
                'total_service_fee': total_service_fee_all,
                'full_total_all_rooms': full_total_all_rooms,
                'active_room_count': len(active_rooms),
                'total_room_count': len(all_rooms),
                'include_tax': include_tax,
                'tax_rate': int(tax_rate * 100),
                'tax_amount': tax_amount,
                'grand_total': grand_total,
                'deposit': deposit,
                'final_total': final_total
            }
        })

    except Exception as e:
        print(f"Lỗi lấy bill đoàn: {e}")
        return jsonify({'success': False, 'msg': 'Lỗi hệ thống: ' + str(e)})


# =======================================================
# 10. XÁC NHẬN THANH TOÁN ĐOÀN (CÁCH 3 - GIỮ CỌC ĐẾN CUỐI)
# =======================================================
@booking_bp.route('/api/bookings/<int:booking_id>/group_checkout', methods=['POST'])
@login_required
def process_group_checkout(booking_id):
    try:
        data = request.get_json() or {}
        include_tax_raw = data.get('include_tax', False)
        include_tax = str(include_tax_raw).strip().lower() in ['1', 'true', 'yes', 'on']
        tax_rate = 0.08

        booking = tenant_get_or_404(Booking, booking_id)
        
        active_rooms = tenant_query(BookingRoom).filter(
            BookingRoom.booking_id == booking_id,
            BookingRoom.status.in_(['booked', 'checked_in'])
        ).all()

        room_totals = []
        total_before_tax = 0.0
        now = datetime.now()

        for br in active_rooms:
            br.status = 'checked_out'
            br.check_out_actual = now
            
            # Tính tiền phòng
            check_in = br.check_in_actual if br.check_in_actual else br.check_in_expected
            room_fee, _ = calculate_complex_hotel_bill(
                check_in, now, br.room,
                rental_type=br.rental_type, 
                expected_check_in=br.check_in_expected, 
                expected_check_out=br.check_out_expected
            )
            
            # Tính tiền dịch vụ (BỔ SUNG ĐỂ HÓA ĐƠN ĐƯỢC CHUẨN XÁC NHẤT)
            service_fee = 0
            room_services = tenant_query(BookingService).filter_by(booking_id=booking.id, room_id=br.room_id).all()
            for svc in room_services:
                service_fee += (svc.quantity * float(svc.price_at_booking or svc.service.price))
            
            room_base_total = room_fee + service_fee
            room_totals.append({
                'booking_room': br,
                'base_total': room_base_total
            })
            total_before_tax += room_base_total
            
            if br.room:
                br.room.status = 'available'
                br.room.clean_status = 'dirty'

        total_tax_amount = round(total_before_tax * tax_rate, 2) if include_tax else 0.0
        total_remaining_amount = total_before_tax + total_tax_amount

        allocated_tax = 0.0
        for idx, info in enumerate(room_totals):
            br = info['booking_room']
            base_total = float(info['base_total'] or 0.0)

            if total_tax_amount > 0 and total_before_tax > 0:
                if idx == len(room_totals) - 1:
                    tax_share = round(total_tax_amount - allocated_tax, 2)
                else:
                    tax_share = round(total_tax_amount * (base_total / total_before_tax), 2)
                    allocated_tax += tax_share
            else:
                tax_share = 0.0

            info['tax_share'] = tax_share
            br.final_amount = base_total + tax_share

        # XỬ LÝ TRỪ CỌC: dùng prepaid_amount còn lại ở cấp booking.
        group_deposit = float(booking.prepaid_amount or 0)
        final_amount_to_pay = total_remaining_amount - group_deposit

        booking.status = 'completed' 
        booking.payment_status = 'paid'
        booking.updated_at = now
        # CẬP NHẬT TỔNG TIỀN ĐƠN (Cho đoàn)
        booking.total_amount = total_remaining_amount
        all_rooms_of_booking = tenant_query(BookingRoom).filter_by(booking_id=booking.id).all()
        for br in all_rooms_of_booking:
            br.room_deposit_amount = 0
        booking.prepaid_amount = 0
        
        # --- GHI NHẬN DOANH THU VÀO SỔ QUỸ (CASHIER) ---
        if total_remaining_amount > 0 and final_amount_to_pay > 0:
            if total_tax_amount > 0 and total_remaining_amount > 0:
                tax_ratio = total_tax_amount / total_remaining_amount
                actual_tax_payment = round(final_amount_to_pay * tax_ratio, 2)
                actual_settlement_payment = round(final_amount_to_pay - actual_tax_payment, 2)
            else:
                actual_tax_payment = 0.0
                actual_settlement_payment = final_amount_to_pay

            if actual_settlement_payment > 0:
                payment_service.record_group_settlement(
                    booking_id=booking.id,
                    amount=actual_settlement_payment,
                    payment_method='cash',
                    note="Thanh toán tổng kết đoàn (Gồm tiền phòng và dịch vụ)",
                    created_at=now,
                )

            if actual_tax_payment > 0:
                if total_tax_amount > 0:
                    allocated_tax_payment = 0.0
                    taxable_rooms = [x for x in room_totals if float(x.get('tax_share') or 0.0) > 0]

                    for idx, info in enumerate(taxable_rooms):
                        br = info['booking_room']
                        room_tax_share = float(info.get('tax_share') or 0.0)

                        if idx == len(taxable_rooms) - 1:
                            room_tax_payment = round(actual_tax_payment - allocated_tax_payment, 2)
                        else:
                            room_tax_payment = round(actual_tax_payment * (room_tax_share / total_tax_amount), 2)
                            allocated_tax_payment += room_tax_payment

                        if room_tax_payment <= 0:
                            continue

                        room_number = br.room.room_number if br.room else br.room_id
                        payment_service.record_room_payment(
                            booking_id=booking.id,
                            amount=room_tax_payment,
                            payment_method='cash',
                            payment_type='tax_payment',
                            note=f"Thuế VAT 8% phòng {room_number} (đoàn {booking.code})",
                            created_at=now,
                        )
                else:
                    payment_service.record_room_payment(
                        booking_id=booking.id,
                        amount=actual_tax_payment,
                        payment_method='cash',
                        payment_type='tax_payment',
                        note=f"Thuế VAT 8% đoàn {booking.code}",
                        created_at=now,
                    )
            
        elif final_amount_to_pay < 0:
            # Hoàn tiền cọc thừa cho khách
            payment_service.record_refund(
                booking_id=booking.id,
                refund_amount=abs(final_amount_to_pay),
                payment_method='cash',
                note="Hoàn cọc thừa cho đoàn",
                created_at=now,
            )

        db.session.commit()
        
        return jsonify({
            'success': True, 
            'msg': 'Thanh toán đoàn thành công!',
            'data': {
                'total_bill': total_remaining_amount, 
                'tax_amount': total_tax_amount,
                'group_deposit': group_deposit,                     
                'final_amount_to_pay': final_amount_to_pay          
            }
        })

    except Exception as e:
        db.session.rollback()
        print(f"Lỗi thanh toán đoàn: {e}")
        return jsonify({'success': False, 'msg': 'Lỗi thanh toán: ' + str(e)})
