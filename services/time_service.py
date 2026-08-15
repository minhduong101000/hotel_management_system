"""Time service duy nhất cho tài chính/báo cáo (spec 14-08-2026, mục 7).

Hợp đồng thời gian:
- Database lưu UTC. Cột DateTime legacy chưa timezone-aware -> lưu UTC-naive;
  helper ở đây là nơi duy nhất gắn/chuyển múi giờ.
- Múi giờ nghiệp vụ (ngày báo cáo, "hôm nay" của lễ tân) là BUSINESS_TIMEZONE,
  mặc định Asia/Bangkok (UTC+7). Chưa hỗ trợ timezone riêng từng khách sạn.
- Test đóng băng đồng hồ bằng monkeypatch time_service.utc_now.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

DEFAULT_BUSINESS_TIMEZONE = "Asia/Bangkok"


def _business_tz() -> ZoneInfo:
    try:  # đọc config nếu đang trong app context, không thì dùng mặc định
        from flask import current_app

        name = current_app.config.get("BUSINESS_TIMEZONE", DEFAULT_BUSINESS_TIMEZONE)
    except RuntimeError:
        name = DEFAULT_BUSINESS_TIMEZONE
    return ZoneInfo(name)


def utc_now() -> datetime:
    """Thời điểm hiện tại, aware UTC. Điểm monkeypatch duy nhất của test."""
    return datetime.now(timezone.utc)


def utc_now_naive() -> datetime:
    """UTC-naive để ghi vào các cột DateTime legacy."""
    return utc_now().replace(tzinfo=None)


def business_now() -> datetime:
    """Giờ nghiệp vụ hiện tại (aware, múi giờ Bangkok)."""
    return utc_now().astimezone(_business_tz())


def business_today() -> date:
    return business_now().date()


def business_period_to_utc(start_date: date, end_date: date):
    """Đổi kỳ báo cáo theo ngày Bangkok thành cửa sổ [start_utc, end_utc) naive-UTC.

    Naive-UTC để so sánh trực tiếp với các cột DateTime legacy đang lưu UTC.
    """
    tz = _business_tz()
    start_local = datetime.combine(start_date, time.min, tzinfo=tz)
    end_local = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
    return (
        start_local.astimezone(timezone.utc).replace(tzinfo=None),
        end_local.astimezone(timezone.utc).replace(tzinfo=None),
    )


def business_day_utc_bounds(business_date: date):
    """Cửa sổ naive-UTC của MỘT ngày nghiệp vụ (cho tính lấp đầy theo ngày)."""
    return business_period_to_utc(business_date, business_date)


def to_business_date(utc_dt: datetime) -> date:
    """Đổi một mốc UTC (naive hoặc aware) về NGÀY nghiệp vụ Bangkok."""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(_business_tz()).date()


def format_business(utc_dt, fmt: str = "%H:%M %d/%m/%Y") -> str:
    """Đổi mốc UTC (naive/aware) sang giờ nghiệp vụ Bangkok để HIỂN THỊ.

    Chỉ dùng cho timestamp hệ thống ghi (created_at, *_actual). KHÔNG dùng
    cho giờ dự kiến do người dùng nhập (check_in_expected...) — chúng vốn đã
    là giờ nghiệp vụ.
    """
    if utc_dt is None:
        return ""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(_business_tz()).strftime(fmt)
