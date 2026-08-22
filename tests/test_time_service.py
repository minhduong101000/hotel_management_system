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


def test_business_now_naive_is_vn_wallclock_without_tzinfo(app, monkeypatch):
    # 03:00 UTC = 10:00 giờ VN
    monkeypatch.setattr(
        time_service, "utc_now", lambda: datetime(2026, 8, 19, 3, 0, tzinfo=timezone.utc)
    )
    with app.app_context():
        result = time_service.business_now_naive()
    assert result == datetime(2026, 8, 19, 10, 0)
    assert result.tzinfo is None


def test_to_business_naive_accepts_naive_and_aware_utc(app):
    with app.app_context():
        assert time_service.to_business_naive(datetime(2026, 8, 19, 3, 0)) == datetime(2026, 8, 19, 10, 0)
        assert time_service.to_business_naive(
            datetime(2026, 8, 19, 3, 0, tzinfo=timezone.utc)
        ) == datetime(2026, 8, 19, 10, 0)
        assert time_service.to_business_naive(None) is None


def test_business_naive_to_utc_is_the_exact_inverse(app):
    with app.app_context():
        business = datetime(2026, 8, 19, 10, 0)
        assert time_service.business_naive_to_utc(business) == datetime(2026, 8, 19, 3, 0)
        assert time_service.to_business_naive(
            time_service.business_naive_to_utc(business)
        ) == business
        assert time_service.business_naive_to_utc(None) is None


def test_utc_naive_from_timestamp_converts_a_posix_stamp():
    from datetime import datetime, timezone

    from services import time_service

    # 2026-08-22 01:30:00 UTC
    stamp = datetime(2026, 8, 22, 1, 30, tzinfo=timezone.utc).timestamp()

    assert time_service.utc_naive_from_timestamp(stamp) == datetime(2026, 8, 22, 1, 30)


def test_utc_naive_from_timestamp_ignores_the_machine_timezone(monkeypatch):
    """Đây là lý do hàm này tồn tại.

    `datetime.fromtimestamp(ts)` trần diễn giải theo giờ MÁY, nên cùng một tệp
    sẽ ra hai kết quả khác nhau giữa máy lập trình (giờ VN) và container
    (UTC) — lệch đúng 7 tiếng, đủ để một bản sao lưu 25 giờ tuổi bị chấm là
    32 giờ và kêu oan mỗi ngày.
    """
    import time as time_module
    from datetime import datetime, timezone

    from services import time_service

    stamp = datetime(2026, 8, 22, 1, 30, tzinfo=timezone.utc).timestamp()
    expected = datetime(2026, 8, 22, 1, 30)

    try:
        for zone in ("UTC", "Asia/Ho_Chi_Minh", "America/New_York"):
            monkeypatch.setenv("TZ", zone)
            time_module.tzset()
            assert time_service.utc_naive_from_timestamp(stamp) == expected
    finally:
        # monkeypatch khôi phục biến môi trường nhưng KHÔNG biết gì về tzset(),
        # nên phải tự đồng bộ lại — kể cả khi assert ở trên đã đỏ. Bỏ qua bước
        # này là để lại giờ hệ thống lệch cho mọi test chạy sau.
        monkeypatch.undo()
        time_module.tzset()
