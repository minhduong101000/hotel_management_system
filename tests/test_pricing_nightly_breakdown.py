from datetime import datetime

from services.pricing_service import get_billable_night_dates


def test_billable_nights_use_the_start_date_of_each_night():
    nights = get_billable_night_dates(
        datetime(2026, 9, 2, 14, 0),
        datetime(2026, 9, 3, 12, 0),
    )

    assert nights == [datetime(2026, 9, 2).date()]


def test_billable_nights_span_each_business_date():
    nights = get_billable_night_dates(
        datetime(2026, 4, 30, 14, 0),
        datetime(2026, 5, 2, 12, 0),
    )

    assert nights == [datetime(2026, 4, 30).date(), datetime(2026, 5, 1).date()]
