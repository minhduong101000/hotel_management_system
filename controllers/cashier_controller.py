from datetime import datetime

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from decorators import admin_required
from models.payment import Payment
from services import payment_service
from services.reporting_service import resolve_report_period
from services.tenant_service import tenant_query

from extensions import db

from services import time_service

cashier_bp = Blueprint('cashier', __name__)

@cashier_bp.route('/reports/cashier')
@login_required
@admin_required
def cashier():
    return render_template('reports/cashier.html')

@cashier_bp.route('/api/reports/cashier')
@login_required
@admin_required
def get_cashier_data():
    try:
        from models.expense import Expense
        from services import time_service

        report_period = resolve_report_period(
            request.args.get('period', 'today'),
            request.args.get('start'),
            request.args.get('end'),
            time_service.business_now().replace(tzinfo=None),
        )
        start_date, end_exclusive = time_service.business_period_to_utc(
            report_period.start_date, report_period.end_date
        )

        # 1. Lấy các khoản thu/hoàn tiền từ Payment
        payments_query = tenant_query(Payment).filter(
            Payment.created_at >= start_date,
            Payment.created_at < end_exclusive
        ).all()

        # 2. Lấy các khoản chi từ Expense
        expenses_query = tenant_query(Expense).filter(
            Expense.created_at >= start_date,
            Expense.created_at < end_exclusive,
            Expense.is_voided.is_(False),
        ).all()

        total_received = 0
        total_refunded = 0
        total_expense = 0
        records = []

        # Map nhân viên thu tiền để hiển thị đối soát
        from models import User as _User
        collector_ids = {p.created_by for p in payments_query if p.created_by}
        collector_names = {}
        if collector_ids:
            collector_names = {
                u.id: u.username
                for u in _User.query.filter(_User.id.in_(collector_ids)).all()
            }

        # Đánh dấu các dòng refund đã bị đảo (sổ nội bộ giữ đủ, chỉ gắn nhãn)
        payment_ids = [p.id for p in payments_query]
        reversed_ids = set()
        if payment_ids:
            reversed_ids = {
                row[0]
                for row in db.session.query(Payment.reverses_payment_id)
                .filter(Payment.reverses_payment_id.in_(payment_ids))
                .all()
            }

        # Xử lý Payment
        #
        # Phân loại total_received / total_refunded theo payment_type, KHÔNG
        # theo dấu của amount. Trước Task 10 chỉ 'refund' mới âm nên gộp theo
        # dấu vô tình đúng; từ khi có 'deposit_adjustment' (cũng âm nhưng
        # KHÔNG phải hoàn tiền cho khách — là đính chính một khoản thu đã ghi
        # sai) thì phải tách tường minh, nếu không KPI "Tổng hoàn cọc" sẽ lẫn
        # hai nghiệp vụ khác hẳn nhau.
        for p in payments_query:
            amt = float(p.amount)
            if p.payment_type == 'refund':
                total_refunded += abs(amt)
            elif p.payment_type == 'deposit_adjustment':
                # Đính chính khoản đã thu bị ghi dư, không phải tiền hoàn cho
                # khách: trừ thẳng vào total_received. net_amount không đổi
                # về số học so với cách gộp theo dấu (received -X thay vì
                # refunded +X), chỉ trả lại đúng ý nghĩa cho từng KPI thành phần.
                total_received -= abs(amt)
            elif amt < 0:
                # Loại thanh toán âm chưa được phân loại tường minh ở trên
                # (ví dụ một payment_type mới thêm sau này). Không được lặng
                # lẽ rơi vào một trong hai nhánh — giữ hành vi cũ (tính vào
                # Tổng hoàn) để không biến mất khỏi báo cáo, nhưng in cảnh báo
                # để bắt buộc phải bổ sung nhánh tường minh khi gặp lại.
                print(
                    f"[cashier] payment_type âm chưa phân loại: "
                    f"{p.payment_type!r} (payment id={p.id}) — tạm tính vào Tổng hoàn."
                )
                total_refunded += abs(amt)
            else:
                total_received += amt

            code = p.booking.code if p.booking else '--'
            customer_name = p.booking.customer.name if p.booking and p.booking.customer else 'Khách'
            
            type_label = ''
            badge_color = 'primary'
            if p.payment_type == 'deposit':
                type_label = 'Nhận cọc'
                badge_color = 'info'
            elif p.payment_type == 'deposit_adjustment':
                type_label = 'Điều chỉnh cọc'
                badge_color = 'dark'
            elif p.payment_type == 'room_payment':
                type_label = 'Thanh toán Phòng'
                badge_color = 'success'
            elif p.payment_type == 'service_payment':
                type_label = 'Thanh toán Dịch vụ'
                badge_color = 'warning'
            elif p.payment_type == 'tax_payment':
                type_label = 'Thuế VAT 8%'
                badge_color = 'primary'
            elif p.payment_type == 'settlement':
                type_label = 'Thanh toán Gộp'
                badge_color = 'success'
            elif p.payment_type == 'cancellation_fee':
                type_label = 'Phí hủy phòng'
                badge_color = 'danger'
            elif p.payment_type == 'refund':
                type_label = 'Hoàn tiền'
                badge_color = 'secondary'
            elif p.payment_type == 'refund_reversal':
                type_label = 'Điều chỉnh hoàn tiền'
                badge_color = 'dark'
            else:
                type_label = 'Khác'

            # Nhãn phương thức hiển thị trên Sổ Quỹ (spec 21-08 §5.1/§7.4):
            # 'deposit_adjustment' là bút toán đính chính — không có tiền thật
            # di chuyển, nên KHÔNG được gắn một phương thức thật (payment_method
            # mặc định 'cash' ở tầng ghi sổ) mà phải hiện nhãn trung tính, nếu
            # không Sổ Quỹ sẽ bịa ra một khoản tiền mặt chưa từng rời két.
            if p.payment_type == 'deposit_adjustment':
                payment_method_label = '—'
            else:
                payment_method_label = payment_service.PAYMENT_METHOD_LABELS.get(
                    p.payment_method, p.payment_method or '—'
                )

            records.append({
                'id': f"p_{p.id}",
                'time_dt': p.created_at,
                'time': time_service.format_business(p.created_at),
                'booking_id': p.booking_id,
                'booking_code': code,
                'customer_name': customer_name,
                'amount': amt,
                'formatted_amount': "{:,.0f}".format(amt) + ' đ',
                'type_raw': p.payment_type,
                'type_label': type_label,
                'badge_color': badge_color,
                'payment_method': p.payment_method,
                'payment_method_label': payment_method_label,
                'is_reversed': p.id in reversed_ids,
                'reverses_payment_id': p.reverses_payment_id,
                'collected_by': collector_names.get(p.created_by, ''),
                'note': p.note or ''
            })

        # Xử lý Expense (Chỉ tính tổng, không thêm vào records table)
        for e in expenses_query:
            amt = float(e.amount or 0)
            total_expense += amt

        # Sắp xếp lại theo thời gian giảm dần
        records.sort(key=lambda x: x['time_dt'], reverse=True)

        return jsonify({
            'success': True,
            'data': {
                'records': records,
                'total_received': total_received,
                'total_refunded': total_refunded,
                'total_expense': total_expense,
                'net_amount': total_received - total_refunded - total_expense,
                'period_label': f"Từ {report_period.start_date.strftime('%d/%m/%Y')} đến {report_period.end_date.strftime('%d/%m/%Y')}"
            }
        })
    except ValueError as e:
        return jsonify({'success': False, 'msg': str(e)}), 400
    except Exception as e:
        print(f"Lỗi sổ quỹ: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'msg': str(e)}), 500
