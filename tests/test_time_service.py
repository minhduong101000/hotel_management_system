from datetime import date, datetime, timezone

from services import time_service


def test_utc_now_is_aware_utc(app):
    with app.app_context():
        now = time_service.utc_now()
        assert now.tzinfo is not None
        assert now.utcoffset().total_seconds() == 0


def test_business_now_is_bangkok(app):
    with app.app_context():
        utc = time_service.utc_now()
        business = time_service.business_now()
        # Asia/Bangkok = UTC+7, không DST
        assert business.utcoffset().total_seconds() == 7 * 3600
        assert abs((business - utc).total_seconds()) < 5


def test_business_period_to_utc_window(app):
    with app.app_context():
        start_utc, end_utc = time_service.business_period_to_utc(
            date(2026, 8, 14), date(2026, 8, 14)
        )
        # Ngày 14-08 Bangkok = [13-08 17:00 UTC, 14-08 17:00 UTC)
        assert start_utc == datetime(2026, 8, 13, 17, 0)
        assert end_utc == datetime(2026, 8, 14, 17, 0)
        assert start_utc.tzinfo is None, "trả naive-UTC để so với cột DateTime legacy"


def test_to_business_date_crosses_midnight(app):
    with app.app_context():
        # 17:30 UTC ngày 13 = 00:30 Bangkok ngày 14
        assert time_service.to_business_date(
            datetime(2026, 8, 13, 17, 30)
        ) == date(2026, 8, 14)
        # 16:30 UTC ngày 13 = 23:30 Bangkok ngày 13
        assert time_service.to_business_date(
            datetime(2026, 8, 13, 16, 30)
        ) == date(2026, 8, 13)
