from datetime import datetime
from zoneinfo import ZoneInfo

from stock_tracker.calendar import is_market_session_open


KST = ZoneInfo("Asia/Seoul")


def test_market_session_open_on_regular_weekday() -> None:
    opened = is_market_session_open(datetime(2026, 5, 12, 9, 10, tzinfo=KST))
    assert opened is True


def test_market_session_closed_on_weekend() -> None:
    opened = is_market_session_open(datetime(2026, 5, 10, 9, 10, tzinfo=KST))
    assert opened is False
