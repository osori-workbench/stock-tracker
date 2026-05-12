from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import exchange_calendars as xcals

KST = ZoneInfo("Asia/Seoul")
XKRX = xcals.get_calendar("XKRX")


def is_market_session_open(now: datetime) -> bool:
    if now.tzinfo is None:
        now = now.replace(tzinfo=KST)
    local_now = now.astimezone(KST)
    return XKRX.is_session(local_now.date())
