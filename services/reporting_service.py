from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True)
class ReportPeriod:
    start: datetime
    end_exclusive: datetime

    @property
    def start_date(self):
        return self.start.date()

    @property
    def end_date(self):
        return (self.end_exclusive - timedelta(days=1)).date()

    def dates(self):
        current = self.start_date
        while current <= self.end_date:
            yield current
            current += timedelta(days=1)


def resolve_report_period(period, start_value=None, end_value=None, now=None):
    now = now or datetime.now()
    today = now.date()

    if period == "week":
        first_day = today - timedelta(days=6)
        last_day = today
    elif period == "month":
        first_day = today.replace(day=1)
        last_day = today
    elif period == "custom" and start_value and end_value:
        first_day = datetime.strptime(start_value, "%Y-%m-%d").date()
        last_day = datetime.strptime(end_value, "%Y-%m-%d").date()
        if last_day < first_day:
            raise ValueError("Ngày kết thúc phải từ ngày bắt đầu trở đi.")
    else:
        first_day = today
        last_day = today

    return ReportPeriod(
        start=datetime.combine(first_day, time.min),
        end_exclusive=datetime.combine(last_day + timedelta(days=1), time.min),
    )


def calculate_occupancy(stays, room_count, report_period, now=None):
    from services import time_service

    now = now or time_service.utc_now_naive()
    daily_occupied_rooms = {}

    for business_date in report_period.dates():
        # Biên NGÀY nghiệp vụ đổi sang cửa sổ UTC để so với mốc UTC trong DB
        day_start, day_end = time_service.business_day_utc_bounds(business_date)
        occupied_room_ids = {
            stay.room_id
            for stay in stays
            if stay.check_in_actual
            and stay.check_in_actual < day_end
            and (stay.check_out_actual or now) > day_start
        }
        daily_occupied_rooms[business_date] = len(occupied_room_ids)

    if room_count <= 0:
        daily_rates = {business_date: 0.0 for business_date in daily_occupied_rooms}
        return 0.0, daily_rates

    daily_rates = {
        business_date: round((occupied / room_count) * 100, 1)
        for business_date, occupied in daily_occupied_rooms.items()
    }
    available_room_nights = room_count * len(daily_occupied_rooms)
    occupied_room_nights = sum(daily_occupied_rooms.values())
    overall_rate = (
        round((occupied_room_nights / available_room_nights) * 100, 1)
        if available_room_nights
        else 0.0
    )
    return overall_rate, daily_rates
