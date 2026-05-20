from datetime import date, datetime
from zoneinfo import ZoneInfo

from stock_tracker.calendar import describe_option_expiry, get_monthly_option_expiry, is_market_session_open


KST = ZoneInfo("Asia/Seoul")


def test_market_session_open_on_regular_weekday() -> None:
    opened = is_market_session_open(datetime(2026, 5, 12, 9, 10, tzinfo=KST))
    assert opened is True


def test_market_session_closed_on_weekend() -> None:
    opened = is_market_session_open(datetime(2026, 5, 10, 9, 10, tzinfo=KST))
    assert opened is False


def test_get_monthly_option_expiry_returns_second_thursday() -> None:
    assert get_monthly_option_expiry(2026, 5) == date(2026, 5, 14)
    assert get_monthly_option_expiry(2026, 6) == date(2026, 6, 11)


def test_get_monthly_option_expiry_adjusts_when_second_thursday_is_holiday() -> None:
    assert get_monthly_option_expiry(2014, 10) == date(2014, 10, 8)


def test_describe_option_expiry_marks_same_day_quarterly_witching() -> None:
    info = describe_option_expiry(date(2026, 6, 11))

    assert info.next_expiry == date(2026, 6, 11)
    assert info.days_until == 0
    assert info.is_today is True
    assert info.is_this_week is True
    assert info.is_quarterly_witching is True
    assert info.label == "오늘은 선물·옵션 동시만기일입니다"


def test_describe_option_expiry_marks_upcoming_weekly_window() -> None:
    info = describe_option_expiry(date(2026, 5, 12))

    assert info.next_expiry == date(2026, 5, 14)
    assert info.days_until == 2
    assert info.is_today is False
    assert info.is_this_week is True
    assert info.is_quarterly_witching is False
    assert info.label == "이번 주 옵션 만기 예정 5/14 (D-2)"


def test_describe_option_expiry_uses_adjusted_expiry_date_in_label() -> None:
    info = describe_option_expiry(date(2014, 10, 7))

    assert info.next_expiry == date(2014, 10, 8)
    assert info.label == "이번 주 옵션 만기 예정 10/8 (D-1)"
