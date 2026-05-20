from __future__ import annotations
from datetime import date, datetime
from zoneinfo import ZoneInfo

import calendar as pycalendar
import exchange_calendars as xcals

from stock_tracker.models import OptionExpiryInfo

KST = ZoneInfo("Asia/Seoul")
XKRX = xcals.get_calendar("XKRX")


def is_market_session_open(now: datetime) -> bool:
    if now.tzinfo is None:
        now = now.replace(tzinfo=KST)
    local_now = now.astimezone(KST)
    return XKRX.is_session(local_now.date())


def get_monthly_option_expiry(year: int, month: int) -> date:
    month_weeks = pycalendar.monthcalendar(year, month)
    thursdays = [week[pycalendar.THURSDAY] for week in month_weeks if week[pycalendar.THURSDAY] != 0]
    expiry = date(year, month, thursdays[1])
    if XKRX.is_session(expiry):
        return expiry
    return XKRX.date_to_session(expiry, direction="previous").date()


def get_next_option_expiry(target_date: date) -> date:
    expiry = get_monthly_option_expiry(target_date.year, target_date.month)
    if target_date <= expiry:
        return expiry
    year = target_date.year + (1 if target_date.month == 12 else 0)
    month = 1 if target_date.month == 12 else target_date.month + 1
    return get_monthly_option_expiry(year, month)


def _format_month_day(value: date) -> str:
    return f"{value.month}/{value.day}"


def describe_option_expiry(target_date: date) -> OptionExpiryInfo:
    next_expiry = get_next_option_expiry(target_date)
    days_until = (next_expiry - target_date).days
    is_today = days_until == 0
    is_this_week = 0 <= days_until <= 6
    is_quarterly_witching = next_expiry.month in {3, 6, 9, 12}

    if is_today and is_quarterly_witching:
        label = "오늘은 선물·옵션 동시만기일입니다"
    elif is_today:
        label = "오늘은 옵션 만기일입니다"
    elif is_this_week:
        label = f"이번 주 옵션 만기 예정 {_format_month_day(next_expiry)} (D-{days_until})"
    else:
        label = f"다음 옵션 만기 {_format_month_day(next_expiry)} (D-{days_until})"

    return OptionExpiryInfo(
        next_expiry=next_expiry,
        days_until=days_until,
        is_today=is_today,
        is_this_week=is_this_week,
        is_quarterly_witching=is_quarterly_witching,
        label=label,
    )
