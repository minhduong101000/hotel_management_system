from datetime import datetime

from services import time_service


def test_format_business_converts_utc_to_bangkok(app):
    with app.app_context():
        # 04:35 UTC = 11:35 gio VN — dung bug hien thi So quy 15-08
        assert time_service.format_business(
            datetime(2026, 8, 15, 4, 35)
        ) == "11:35 15/08/2026"
        # Qua nua dem: 17:30 UTC 14-08 = 00:30 VN 15-08
        assert time_service.format_business(
            datetime(2026, 8, 14, 17, 30), "%d/%m/%Y %H:%M"
        ) == "15/08/2026 00:30"


def test_format_business_handles_none(app):
    with app.app_context():
        assert time_service.format_business(None) == ""
