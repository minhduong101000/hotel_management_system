from datetime import datetime

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required
from sqlalchemy import func

from decorators import admin_required
from extensions import db
from models.booking import Booking
from models.booking_room import BookingRoom
from models.expense import Expense
from models.payment import Payment
from models.room import Room
from services.reporting_service import calculate_occupancy, resolve_report_period
from services.tenant_service import current_hotel_id, tenant_query


from services import time_service

report_bp = Blueprint("report", __name__)


@report_bp.route("/reports/revenue")
@login_required
@admin_required
def revenue():
    return render_template("reports/revenue.html")


@report_bp.route("/api/reports/revenue")
@login_required
@admin_required
def get_revenue_data():
    try:
        # Kỳ báo cáo chọn theo NGÀY Bangkok, truy vấn theo cửa sổ UTC tương ứng
        now_utc = time_service.utc_now_naive()
        report_period = resolve_report_period(
            request.args.get("period", "today"),
            request.args.get("start"),
            request.args.get("end"),
            time_service.business_now().replace(tzinfo=None),
        )
        start_at, end_exclusive = time_service.business_period_to_utc(
            report_period.start_date, report_period.end_date
        )
        hotel_id = current_hotel_id()
        finalized_time = func.coalesce(
            BookingRoom.check_out_actual,
            Booking.updated_at,
        )

        room_revenue = (
            db.session.query(func.coalesce(func.sum(BookingRoom.final_amount), 0))
            .select_from(BookingRoom)
            .join(Booking, Booking.id == BookingRoom.booking_id)
            .filter(
                BookingRoom.hotel_id == hotel_id,
                Booking.hotel_id == hotel_id,
                BookingRoom.status.in_(["checked_out", "cancelled"]),
                finalized_time >= start_at,
                finalized_time < end_exclusive,
            )
            .scalar()
        )

        total_cash_in = (
            db.session.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(
                Payment.hotel_id == hotel_id,
                Payment.amount > 0,
                Payment.created_at >= start_at,
                Payment.created_at < end_exclusive,
            )
            .scalar()
        )
        total_cash_out = (
            db.session.query(func.coalesce(func.sum(func.abs(Payment.amount)), 0))
            .filter(
                Payment.hotel_id == hotel_id,
                Payment.amount < 0,
                Payment.created_at >= start_at,
                Payment.created_at < end_exclusive,
            )
            .scalar()
        )

        # Đếm theo mốc hoàn tất nghiệp vụ, không dùng updated_at (mốc kỹ thuật)
        completed_bookings = tenant_query(Booking).filter(
            Booking.status == "completed",
            Booking.completed_at.isnot(None),
            Booking.completed_at >= start_at,
            Booking.completed_at < end_exclusive,
        ).count()

        expense_filters = (
            Expense.hotel_id == hotel_id,
            Expense.is_voided.is_(False),
            Expense.expense_date >= report_period.start_date,
            Expense.expense_date <= report_period.end_date,
        )
        total_expenses = (
            db.session.query(func.coalesce(func.sum(Expense.amount), 0))
            .filter(*expense_filters)
            .scalar()
        )

        # Không dùng func.date() theo timezone của dialect — lấy mốc thô rồi
        # gom theo NGÀY Bangkok trong Python (SQLite trả UTC, MySQL theo server)
        finalized_rows = (
            db.session.query(
                finalized_time.label("finalized_at"),
                BookingRoom.final_amount.label("revenue"),
            )
            .select_from(BookingRoom)
            .join(Booking, Booking.id == BookingRoom.booking_id)
            .filter(
                BookingRoom.hotel_id == hotel_id,
                Booking.hotel_id == hotel_id,
                BookingRoom.status.in_(["checked_out", "cancelled"]),
                finalized_time >= start_at,
                finalized_time < end_exclusive,
            )
            .all()
        )
        revenue_by_business_date = {}
        for row in finalized_rows:
            business_date = time_service.to_business_date(row.finalized_at)
            revenue_by_business_date[business_date] = (
                revenue_by_business_date.get(business_date, 0.0)
                + float(row.revenue or 0)
            )
        daily_expenses = (
            db.session.query(
                Expense.expense_date.label("date"),
                func.sum(Expense.amount).label("expense"),
            )
            .filter(*expense_filters)
            .group_by(Expense.expense_date)
            .all()
        )

        room_count = tenant_query(Room).count()
        stays = tenant_query(BookingRoom).filter(
            BookingRoom.status.in_(["checked_in", "checked_out"]),
            BookingRoom.check_in_actual.isnot(None),
            BookingRoom.check_in_actual < end_exclusive,
            func.coalesce(BookingRoom.check_out_actual, now_utc) > start_at,
        ).all()
        occupancy_rate, daily_occupancy = calculate_occupancy(
            stays,
            room_count,
            report_period,
            now_utc,
        )

        chart_map = {
            business_date: {
                "revenue": 0.0,
                "expense": 0.0,
                "occupancy_rate": daily_occupancy[business_date],
            }
            for business_date in report_period.dates()
        }

        def as_date(value):
            if isinstance(value, str):
                return datetime.strptime(value[:10], "%Y-%m-%d").date()
            if isinstance(value, datetime):
                return value.date()
            return value

        for business_date, revenue in revenue_by_business_date.items():
            if business_date in chart_map:
                chart_map[business_date]["revenue"] = revenue
        for row in daily_expenses:
            business_date = as_date(row.date)
            if business_date in chart_map:
                chart_map[business_date]["expense"] = float(row.expense or 0)

        chart_data = []
        for business_date, values in chart_map.items():
            chart_data.append(
                {
                    **values,
                    "date": business_date.strftime("%d/%m"),
                }
            )

        top_rooms = (
            db.session.query(
                BookingRoom.room_id,
                Room.room_number,
                Room.room_type,
                func.count(BookingRoom.id).label("count"),
                func.sum(BookingRoom.final_amount).label("total"),
            )
            .select_from(BookingRoom)
            .join(Booking, Booking.id == BookingRoom.booking_id)
            .join(Room, Room.id == BookingRoom.room_id)
            .filter(
                BookingRoom.hotel_id == hotel_id,
                Booking.hotel_id == hotel_id,
                Room.hotel_id == hotel_id,
                BookingRoom.status.in_(["checked_out", "cancelled"]),
                finalized_time >= start_at,
                finalized_time < end_exclusive,
            )
            .group_by(BookingRoom.room_id, Room.room_number, Room.room_type)
            .order_by(func.sum(BookingRoom.final_amount).desc())
            .limit(5)
            .all()
        )
        top_rooms_data = [
            {
                "room_number": row.room_number,
                "room_type": row.room_type,
                "count": row.count,
                "total": float(row.total or 0),
            }
            for row in top_rooms
        ]

        room_revenue_value = float(room_revenue or 0)
        expense_value = float(total_expenses or 0)
        return jsonify(
            {
                "success": True,
                "data": {
                    "room_revenue": room_revenue_value,
                    "total_net_payment": float(total_cash_in or 0)
                    - float(total_cash_out or 0),
                    "total_expenses": expense_value,
                    "net_profit": room_revenue_value - expense_value,
                    "completed_bookings": completed_bookings,
                    "occupancy_rate": occupancy_rate,
                    "chart": chart_data,
                    "top_rooms": top_rooms_data,
                    "period": {
                        "start": report_period.start_date.strftime("%d/%m/%Y"),
                        "end": report_period.end_date.strftime("%d/%m/%Y"),
                    },
                },
            }
        )
    except ValueError as error:
        return jsonify({"success": False, "msg": str(error)}), 400
    except Exception as error:
        print(f"Lỗi báo cáo doanh thu: {error}")
        return jsonify({"success": False, "msg": str(error)}), 500
