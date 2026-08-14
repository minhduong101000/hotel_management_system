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
from services import (
    booking_state_service,
    booking_quote_service,
    business_operation_service,
    group_checkout_service,
    inventory_service,
    payment_service,
    room_checkout_service,
)
from services import audit_service

booking_bp = Blueprint('booking', __name__)


def _resolve_active_booking_room(room, booking_id=None, booking_room_id=None):
    """Tìm đúng booking_room đang ở; không tự sửa trạng thái nghiệp vụ."""
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
    return None


def _checkout_request_payload(data, booking_room_id):
    """Chuẩn hóa phần request có ảnh hưởng đến kết quả checkout."""
    include_tax = str(data.get('include_tax', False)).strip().lower() in [
        '1', 'true', 'yes', 'on'
    ]
    return {
        'booking_room_id': int(booking_room_id),
        'include_tax': include_tax,
        'payment_method': str(data.get('payment_method') or 'cash').strip().lower(),
        'quote_fingerprint': str(data.get('quote_fingerprint') or ''),
        'quote_checkout_at': str(data.get('quote_checkout_at') or ''),
    }


def _group_checkout_request_payload(data, booking_id):
    """Chuẩn hóa request checkout đoàn và bỏ qua số tiền từ client."""
    include_tax = str(data.get('include_tax', False)).strip().lower() in [
        '1', 'true', 'yes', 'on'
    ]
    return {
        'booking_id': int(booking_id),
        'include_tax': include_tax,
        'payment_method': str(data.get('payment_method') or 'cash').strip().lower(),
        'quote_fingerprint': str(data.get('quote_fingerprint') or ''),
        'quote_checkout_at': str(data.get('quote_checkout_at') or ''),
    }


def _service_mutation_booking_room(data):
    """Khóa và xác thực phòng trước mọi thay đổi hóa đơn dịch vụ."""
    booking_room_id = data.get('booking_room_id')
    if not booking_room_id:
        return None, (
            jsonify({
                'success': False,
                'error_code': 'booking_room_required',
                'msg': 'Thiếu booking_room_id.',
            }),
            400,
        )
    try:
        booking_room_id = int(booking_room_id)
    except (TypeError, ValueError):
        return None, (
            jsonify({
                'success': False,
                'error_code': 'booking_room_required',
                'msg': 'booking_room_id không hợp lệ.',
            }),
            400,
        )

    booking_room = tenant_query(BookingRoom).filter_by(
        id=booking_room_id
    ).with_for_update().first()
    if booking_room is None:
        return None, (
            jsonify({
                'success': False,
                'error_code': 'booking_room_not_found',
                'msg': 'Không tìm thấy phòng trong booking.',
            }),
            404,
        )
    if booking_room.status != 'checked_in':
        return None, (
            jsonify({
                'success': False,
                'error_code': 'service_bill_finalized',
                'msg': 'Hóa đơn dịch vụ của phòng đã được chốt.',
            }),
            409,
        )
    return booking_room, None

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

    booking_state_service.check_in_room(
        booking_room,
        checked_in_at=now,
    )

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
        data = request.get_json(silent=True) or {}
        service_id = data.get('service_id')
        if not service_id:
            return jsonify({
                'success': False,
                'msg': 'Thiếu thông tin dịch vụ.',
            }), 400
        try:
            service_id = int(service_id)
            change = int(data.get('change', 0))
        except (TypeError, ValueError):
            return jsonify({
                'success': False,
                'msg': 'Dữ liệu số lượng không hợp lệ.',
            }), 400

        booking_room, error_response = _service_mutation_booking_room(data)
        if error_response:
            return error_response

        line_item = tenant_query(BookingService).filter_by(
            booking_id=booking_room.booking_id,
            room_id=booking_room.room_id,
            service_id=service_id,
        ).with_for_update().first()

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
                service_id: applied_change
            })
            inventory_service.deduct_inventory(
                line_item.hotel_id,
                service_id,
                applied_change,
                booking_service=line_item,
            )
        elif applied_change < 0:
            inventory_service.restore_inventory(
                line_item.hotel_id,
                service_id,
                -applied_change,
                booking_service=line_item,
            )

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
        return jsonify({
            'success': False,
            'error_code': 'insufficient_inventory',
            'msg': str(e),
        }), 409
    except Exception:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error_code': 'service_update_failed',
            'msg': 'Không thể cập nhật dịch vụ.',
        }), 500

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

    booking_room = _resolve_active_booking_room(
        room=room,
        booking_id=booking_id,
    )

    if not booking_room:
        return jsonify({'success': False, 'msg': 'Không tìm thấy phòng đang check-in để thanh toán.'})

    check_in_time = booking_room.check_in_actual or booking_room.check_in_expected or datetime.now()
    check_out_time = datetime.now().replace(microsecond=0)
    quote = booking_quote_service.build_checkout_quote(
        booking_room,
        checkout_at=check_out_time,
        include_tax=include_tax,
    )

    room_fee = float(quote['room_subtotal'])
    service_fee = float(quote['service_subtotal'])
    tax_amount = float(quote['tax'])
    total_bill = float(quote['total'])
    prepaid_amount = float(quote['deposit'])
    final_amount = float(quote['balance'])
    apply_deposit_now = quote['apply_deposit']
    breakdown = [
        {
            **line,
            'amount': float(line['amount']),
        }
        for line in quote['room_lines']
    ]
    services_data = [
        {
            'service_id': line['service_id'],
            'name': line['name'],
            'quantity': line['quantity'],
            'price': float(line['unit_price']),
            'total': float(line['amount']),
        }
        for line in quote['service_lines']
    ]

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
        'tax_rate': int(float(quote['tax_rate']) * 100),
        'tax_amount': tax_amount,
        'formatted_tax_amount': _format_vnd(tax_amount),
        'formatted_total_bill': _format_vnd(total_bill),
        'apply_deposit_now': apply_deposit_now,
        'prepaid_amount': prepaid_amount,
        'formatted_prepaid_amount': _format_vnd(prepaid_amount),
        'final_amount': final_amount,
        'formatted_final_amount': f"{_format_vnd(final_amount)} đ",
        'quote': quote,
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
    include_tax_raw = data.get('include_tax', False)
    include_tax = str(include_tax_raw).strip().lower() in ['1', 'true', 'yes', 'on']

    room = tenant_query(Room).filter(Room.room_number == room_number).first()
    if not room:
        return jsonify({
            'success': False,
            'error_code': 'room_not_found',
            'msg': 'Phòng không tồn tại.',
        }), 404

    if booking_room_id:
        completed_booking_room = tenant_query(BookingRoom).filter_by(
            id=booking_room_id,
            room_id=room.id,
            status='checked_out',
        ).first()
        if completed_booking_room:
            operation_key = f'checkout:{completed_booking_room.id}'
            existing_operation = tenant_query(BusinessOperation).filter_by(
                operation_key=operation_key
            ).first()
            if existing_operation:
                operation_request = _checkout_request_payload(
                    data,
                    completed_booking_room.id,
                )
                try:
                    return jsonify(
                        business_operation_service.replay_operation(
                            existing_operation,
                            operation_request,
                        )
                    )
                except business_operation_service.OperationRequestConflict as error:
                    return jsonify({
                        'success': False,
                        'msg': str(error),
                        'operation_key': operation_key,
                    }), 409
                except business_operation_service.OperationInProgress:
                    return jsonify({
                        'success': False,
                        'msg': 'Phòng này đang được checkout bởi thao tác khác.',
                        'operation_key': operation_key,
                    }), 409
            return jsonify({
                'success': False,
                'msg': 'Phòng này đã checkout.',
                'operation_key': operation_key,
            }), 409

    booking_room = _resolve_active_booking_room(
        room=room,
        booking_id=booking_id,
        booking_room_id=booking_room_id,
    )

    if not booking_room:
        invalid_query = tenant_query(BookingRoom).filter_by(room_id=room.id)
        if booking_room_id:
            invalid_query = invalid_query.filter_by(id=booking_room_id)
        if booking_id:
            invalid_query = invalid_query.filter_by(booking_id=booking_id)
        invalid_booking_room = invalid_query.first()
        if invalid_booking_room:
            return jsonify({
                'success': False,
                'error_code': 'invalid_checkout_state',
                'msg': 'Chỉ phòng đang ở mới được phép checkout.',
                'current_status': invalid_booking_room.status,
            }), 409
        return jsonify({
            'success': False,
            'error_code': 'booking_room_not_found',
            'msg': 'Không tìm thấy đơn để thanh toán.',
        }), 404

    fresh_quote = booking_quote_service.build_checkout_quote(
        booking_room,
        checkout_at=datetime.now().replace(microsecond=0),
        include_tax=include_tax,
    )
    quote_fingerprint = str(data.get('quote_fingerprint') or '')
    quote_checkout_at_raw = data.get('quote_checkout_at')
    try:
        quote_checkout_at = datetime.fromisoformat(
            str(quote_checkout_at_raw)
        ).replace(tzinfo=None, microsecond=0)
        checkout_quote = booking_quote_service.build_checkout_quote(
            booking_room,
            checkout_at=quote_checkout_at,
            include_tax=include_tax,
        )
    except (TypeError, ValueError):
        checkout_quote = None

    if (
        checkout_quote is None
        or not quote_fingerprint
        or checkout_quote['fingerprint'] != quote_fingerprint
        or booking_quote_service.is_expired(checkout_quote)
    ):
        return jsonify({
            'success': False,
            'error_code': 'quote_stale',
            'msg': 'Báo giá đã thay đổi hoặc hết hạn. Vui lòng kiểm tra báo giá mới.',
            'quote': fresh_quote,
        }), 409

    now = quote_checkout_at
    operation_key = f'checkout:{booking_room.id}'
    operation_request = _checkout_request_payload(data, booking_room.id)
    existing_operation = tenant_query(BusinessOperation).filter_by(
        operation_key=operation_key
    ).first()
    if existing_operation:
        try:
            return jsonify(
                business_operation_service.replay_operation(
                    existing_operation,
                    operation_request,
                )
            )
        except business_operation_service.OperationRequestConflict as error:
            return jsonify({
                'success': False,
                'msg': str(error),
                'operation_key': operation_key,
            }), 409
        except business_operation_service.OperationInProgress:
            return jsonify({
                'success': False,
                'msg': 'Phòng này đang được checkout bởi thao tác khác.',
                'operation_key': operation_key,
            }), 409

    operation = BusinessOperation(
        hotel_id=room.hotel_id,
        operation_key=operation_key,
        action='checkout',
        entity_type='booking_room',
        entity_id=booking_room.id,
        request_fingerprint=business_operation_service.request_fingerprint(
            operation_request
        ),
    )
    db.session.add(operation)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        existing_operation = tenant_query(BusinessOperation).filter_by(
            operation_key=operation_key
        ).first()
        if existing_operation:
            try:
                return jsonify(
                    business_operation_service.replay_operation(
                        existing_operation,
                        operation_request,
                    )
                )
            except (
                business_operation_service.OperationRequestConflict,
                business_operation_service.OperationInProgress,
            ):
                pass
        return jsonify({
            'success': False,
            'msg': 'Phòng này đang được checkout bởi thao tác khác.',
            'operation_key': operation_key,
        }), 409

    try:
        result_payload = room_checkout_service.settle_room_checkout(
            booking_room=booking_room,
            quote=checkout_quote,
            operation=operation,
            payment_method=data.get('payment_method'),
            checkout_at=now,
            actor_user_id=current_user.id,
        )
        db.session.commit()
        return jsonify(result_payload)
    except booking_state_service.InvalidBookingTransition as error:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error_code': 'invalid_checkout_state',
            'msg': str(error),
        }), 409
    except Exception:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error_code': 'checkout_failed',
            'msg': 'Không thể hoàn tất checkout. Dữ liệu chưa được thay đổi.',
        }), 500

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
    ).filter(
        BookingService.quantity > 0
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
    return jsonify({
        'booking_room_id': booking_room.id,
        'items': items,
        'total': sum(item['total'] for item in items),
    })


@booking_bp.route('/api/orders/add', methods=['POST'])
@login_required
def add_order():
    try:
        data = request.get_json(silent=True) or {}
        room_number = data.get('room_number')
        items = data.get('items')

        br, error_response = _service_mutation_booking_room(data)
        if error_response:
            return error_response

        if not isinstance(items, list) or not items:
            return jsonify({'success': False, 'msg': 'Cần chọn ít nhất một dịch vụ.'}), 400

        room = br.room
        if room_number and str(room.room_number) != str(room_number):
            return jsonify({
                'success': False,
                'error_code': 'booking_room_mismatch',
                'msg': 'Phòng không khớp với booking_room_id.',
            }), 409

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
                db.session.flush()
                line_item = existing
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
                db.session.flush()
                line_item = new_bs

            inventory_service.deduct_inventory(room.hotel_id, s_id, qty, booking_service=line_item)

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
        return jsonify({
            'success': False,
            'error_code': 'insufficient_inventory',
            'msg': str(e),
        }), 409
    except Exception:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error_code': 'order_failed',
            'msg': 'Không thể ghi nhận dịch vụ.',
        }), 500

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

        price_quote = booking_quote_service.build_new_booking_quote(
            rooms_query,
            check_in=check_in,
            check_out=check_out,
            rental_type='daily',
        )
        estimated_total = float(price_quote['total'])

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
            successful_rooms = [
                room_dict[br.room_id]
                for br in created_rooms
                if br.room_id in room_dict
            ]
            successful_quote = booking_quote_service.build_new_booking_quote(
                successful_rooms,
                check_in=check_in,
                check_out=check_out,
                rental_type='daily',
            )
            estimated_total_success = float(successful_quote['total'])

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

            booking_state_service.aggregate_booking_state(
                new_booking,
                changed_at=datetime.now(),
            )

            audit_service.record_event(
                hotel_id=g.hotel_id,
                actor_user_id=current_user.id,
                action='create_group_booking',
                entity_type='booking',
                entity_id=new_booking.id,
                after_data={
                    'booking_code': new_booking.code,
                    'room_ids': [room_row.room_id for room_row in created_rooms],
                    'check_in': check_in.isoformat(),
                    'check_out': check_out.isoformat(),
                    'deposit': total_deposit,
                    'customer_id': customer.id,
                },
            )

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
    data = request.get_json(silent=True) or {}
    room_number = data.get('number')
    new_services = data.get('services', [])

    try:
        booking_room, error_response = _service_mutation_booking_room(data)
        if error_response:
            return error_response
        room = booking_room.room
        if room_number and str(room.room_number) != str(room_number):
            return jsonify({
                'success': False,
                'error_code': 'booking_room_mismatch',
                'msg': 'Phòng không khớp với booking_room_id.',
            }), 409
        if not isinstance(new_services, list):
            return jsonify({
                'success': False,
                'msg': 'Danh sách dịch vụ không hợp lệ.',
            }), 400

        booking = booking_room.booking
        normalized_by_service = {}
        for item in new_services:
            try:
                service_id = int(item['service_id'])
                quantity = int(item['quantity'])
            except (KeyError, TypeError, ValueError):
                return jsonify({
                    'success': False,
                    'msg': 'Dữ liệu dịch vụ không hợp lệ.',
                }), 400
            if quantity < 0:
                return jsonify({
                    'success': False,
                    'msg': 'Số lượng dịch vụ không được âm.',
                }), 400
            if quantity <= 0:
                continue
            service_obj = tenant_query(Service).filter_by(id=service_id).first()
            if not service_obj:
                return jsonify({'success': False, 'msg': 'Dịch vụ không thuộc khách sạn hiện tại.'}), 404
            if service_id in normalized_by_service:
                normalized_by_service[service_id]['quantity'] += quantity
            else:
                normalized_by_service[service_id] = {
                    'quantity': quantity,
                    'service': service_obj,
                }

        old_items = tenant_query(BookingService).filter_by(
            booking_id=booking.id,
            room_id=room.id,
        ).order_by(BookingService.id.asc()).with_for_update().all()
        old_by_service = {
            item.service_id: item
            for item in old_items
        }
        before_services = [
            {
                'service_id': item.service_id,
                'quantity': int(item.quantity or 0),
                'unit_price': float(item.price_at_booking or 0),
            }
            for item in old_items
        ]
        all_service_ids = set(old_by_service) | set(normalized_by_service)
        positive_deltas = {}
        for service_id in all_service_ids:
            old_quantity = (
                int(old_by_service[service_id].quantity or 0)
                if service_id in old_by_service
                else 0
            )
            new_quantity = normalized_by_service.get(
                service_id,
                {'quantity': 0},
            )['quantity']
            positive_deltas[service_id] = max(
                0,
                new_quantity - old_quantity,
            )
        inventory_service.validate_inventory(room.hotel_id, positive_deltas)

        for service_id in sorted(all_service_ids):
            desired = normalized_by_service.get(
                service_id,
                {'quantity': 0, 'service': None},
            )
            quantity = desired['quantity']
            line_item = old_by_service.get(service_id)
            if line_item is None:
                if quantity <= 0:
                    continue
                line_item = BookingService(
                    hotel_id=room.hotel_id,
                    booking_id=booking.id,
                    room_id=room.id,
                    service_id=service_id,
                    quantity=0,
                    price_at_booking=desired['service'].price,
                )
                db.session.add(line_item)
                db.session.flush()
            current_quantity = int(line_item.quantity or 0)
            delta = quantity - current_quantity
            if delta > 0:
                inventory_service.deduct_inventory(
                    room.hotel_id,
                    service_id,
                    delta,
                    booking_service=line_item,
                )
            elif delta < 0:
                inventory_service.restore_inventory(
                    room.hotel_id,
                    service_id,
                    -delta,
                    booking_service=line_item,
                )
            line_item.quantity = quantity

        audit_service.record_event(
            hotel_id=room.hotel_id,
            actor_user_id=current_user.id,
            action='update_group_booking_services',
            entity_type='booking',
            entity_id=booking.id,
            before_data={
                'room_id': room.id,
                'services': before_services,
            },
            after_data={
                'room_id': room.id,
                'services': [
                    {
                        'service_id': service_id,
                        'quantity': values['quantity'],
                        'unit_price': float(values['service'].price or 0),
                    }
                    for service_id, values in sorted(
                        normalized_by_service.items()
                    )
                ],
            },
        )
        
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Đã cập nhật dịch vụ và tồn kho.'})

    except inventory_service.InsufficientInventoryError as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error_code': 'insufficient_inventory',
            'msg': str(e),
        }), 409
    except Exception:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error_code': 'service_update_failed',
            'msg': 'Không thể cập nhật danh sách dịch vụ.',
        }), 500


# =======================================================
# 9. LẤY THÔNG TIN HÓA ĐƠN ĐOÀN (MỚI THÊM)
# =======================================================
@booking_bp.route('/api/bookings/<int:booking_id>/group_billing', methods=['GET'])
@login_required
def get_group_billing(booking_id):
    try:
        include_tax_raw = request.args.get('include_tax', 'false')
        include_tax = str(include_tax_raw).strip().lower() in ['1', 'true', 'yes', 'on']
        booking = tenant_get_or_404(Booking, booking_id)
        if not booking.rooms:
            return jsonify({'success': False, 'msg': 'Booking này chưa có phòng nào.'})

        quote = booking_quote_service.build_group_checkout_quote(
            booking,
            checkout_at=datetime.now().replace(microsecond=0),
            include_tax=include_tax,
        )
        status_label_map = {
            'booked': 'Chưa nhận',
            'checked_in': 'Đang ở',
            'checked_out': 'Đã trả',
            'cancelled': 'Đã hủy',
        }
        room_details = []
        service_summary_map = {}
        for room_quote in quote['rooms']:
            service_items = []
            for service_line in room_quote['service_lines']:
                service_item = {
                    'service_id': service_line['service_id'],
                    'name': service_line['name'],
                    'quantity': service_line['quantity'],
                    'price': float(service_line['unit_price']),
                    'total': float(service_line['amount']),
                }
                service_items.append(service_item)
                summary = service_summary_map.setdefault(
                    service_line['service_id'],
                    {
                        'service_id': service_line['service_id'],
                        'name': service_line['name'],
                        'quantity': 0,
                        'total': 0.0,
                    },
                )
                summary['quantity'] += service_line['quantity']
                summary['total'] += float(service_line['amount'])

            room_details.append({
                'booking_room_id': room_quote['booking_room_id'],
                'room_id': room_quote['room_id'],
                'room_name': room_quote['room_number'],
                'status': room_quote['status'],
                'status_label': status_label_map.get(
                    room_quote['status'],
                    room_quote['status'],
                ),
                'include_in_settlement': room_quote['include_in_settlement'],
                'room_fee': float(room_quote['room_subtotal']),
                'service_fee': float(room_quote['service_subtotal']),
                'tax_amount': float(room_quote['tax']),
                'subtotal': float(room_quote['total']),
                'service_items': service_items,
                'breakdown': [
                    {
                        **line,
                        'amount': float(line['amount']),
                    }
                    for line in room_quote['room_lines']
                ],
            })

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
                'total_room_fee': float(quote['room_subtotal']),
                'total_service_fee': float(quote['service_subtotal']),
                'full_total_all_rooms': float(quote['booking_total']),
                'active_room_count': (
                    len(quote['state_groups']['checked_in'])
                    + len(quote['state_groups']['booked'])
                ),
                'total_room_count': len(quote['rooms']),
                'include_tax': include_tax,
                'tax_rate': int(float(quote['tax_rate']) * 100),
                'tax_amount': float(quote['tax']),
                'grand_total': float(quote['settlement_subtotal']),
                'deposit': float(quote['deposit']),
                'final_total': float(quote['balance']),
                'blocked_room_numbers': quote['state_groups']['booked'],
                'quote': quote,
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error_code': 'group_quote_failed',
            'msg': 'Không thể tải báo giá checkout đoàn.',
        }), 500


# =======================================================
# 10. XÁC NHẬN THANH TOÁN ĐOÀN (CÁCH 3 - GIỮ CỌC ĐẾN CUỐI)
# =======================================================
@booking_bp.route('/api/bookings/<int:booking_id>/group_checkout', methods=['POST'])
@login_required
def process_group_checkout(booking_id):
    data = request.get_json() or {}
    include_tax_raw = data.get('include_tax', False)
    include_tax = str(include_tax_raw).strip().lower() in [
        '1', 'true', 'yes', 'on'
    ]
    operation_key = f'checkout_group:booking:{booking_id}'
    operation_request = _group_checkout_request_payload(data, booking_id)

    booking = tenant_query(Booking).filter_by(id=booking_id).with_for_update().first()
    if booking is None:
        return jsonify({
            'success': False,
            'error_code': 'booking_not_found',
            'msg': 'Không tìm thấy booking đoàn.',
        }), 404

    existing_operation = tenant_query(BusinessOperation).filter_by(
        operation_key=operation_key
    ).with_for_update().first()
    if existing_operation:
        try:
            return jsonify(
                business_operation_service.replay_operation(
                    existing_operation,
                    operation_request,
                )
            )
        except business_operation_service.OperationRequestConflict as error:
            return jsonify({
                'success': False,
                'error_code': 'operation_request_conflict',
                'msg': str(error),
                'operation_key': operation_key,
            }), 409
        except business_operation_service.OperationInProgress:
            return jsonify({
                'success': False,
                'error_code': 'operation_in_progress',
                'msg': 'Booking đoàn đang được checkout bởi thao tác khác.',
                'operation_key': operation_key,
            }), 409

    booking_rooms = tenant_query(BookingRoom).filter_by(
        booking_id=booking.id
    ).order_by(BookingRoom.id.asc()).with_for_update().all()
    booked_rooms = [
        room for room in booking_rooms
        if room.status == 'booked'
    ]
    if booked_rooms:
        return jsonify({
            'success': False,
            'error_code': 'rooms_not_checked_in',
            'msg': 'Cần check-in hoặc hủy các phòng chưa nhận trước khi checkout đoàn.',
            'room_numbers': [
                room.room.room_number for room in booked_rooms
            ],
        }), 409

    checked_in_rooms = [
        room for room in booking_rooms
        if room.status == 'checked_in'
    ]
    if not checked_in_rooms:
        return jsonify({
            'success': False,
            'error_code': 'no_rooms_checked_in',
            'msg': 'Không còn phòng đang ở để checkout đoàn.',
        }), 409

    fresh_quote = booking_quote_service.build_group_checkout_quote(
        booking,
        checkout_at=datetime.now().replace(microsecond=0),
        include_tax=include_tax,
    )
    try:
        quote_checkout_at = datetime.fromisoformat(
            operation_request['quote_checkout_at']
        ).replace(tzinfo=None, microsecond=0)
        checkout_quote = booking_quote_service.build_group_checkout_quote(
            booking,
            checkout_at=quote_checkout_at,
            include_tax=include_tax,
        )
    except (TypeError, ValueError):
        checkout_quote = None

    if (
        checkout_quote is None
        or not operation_request['quote_fingerprint']
        or checkout_quote['fingerprint']
        != operation_request['quote_fingerprint']
        or booking_quote_service.is_expired(checkout_quote)
    ):
        return jsonify({
            'success': False,
            'error_code': 'quote_stale',
            'msg': 'Báo giá đoàn đã thay đổi hoặc hết hạn.',
            'quote': fresh_quote,
        }), 409

    operation = BusinessOperation(
        hotel_id=booking.hotel_id,
        operation_key=operation_key,
        action='group_checkout',
        entity_type='booking',
        entity_id=booking.id,
        request_fingerprint=business_operation_service.request_fingerprint(
            operation_request
        ),
    )
    db.session.add(operation)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        existing_operation = tenant_query(BusinessOperation).filter_by(
            operation_key=operation_key
        ).first()
        if existing_operation:
            try:
                return jsonify(
                    business_operation_service.replay_operation(
                        existing_operation,
                        operation_request,
                    )
                )
            except (
                business_operation_service.OperationRequestConflict,
                business_operation_service.OperationInProgress,
            ):
                pass
        return jsonify({
            'success': False,
            'error_code': 'operation_in_progress',
            'msg': 'Booking đoàn đang được checkout bởi thao tác khác.',
            'operation_key': operation_key,
        }), 409

    try:
        result = group_checkout_service.settle_group_checkout(
            booking=booking,
            booking_rooms=checked_in_rooms,
            quote=checkout_quote,
            operation=operation,
            payment_method=data.get('payment_method'),
            checkout_at=quote_checkout_at,
            actor_user_id=current_user.id,
        )
        db.session.commit()
        return jsonify(result)
    except booking_state_service.InvalidBookingTransition as error:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error_code': 'invalid_group_checkout_state',
            'msg': str(error),
        }), 409
    except Exception:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error_code': 'group_checkout_failed',
            'msg': 'Không thể hoàn tất checkout đoàn. Dữ liệu chưa được thay đổi.',
        }), 500
