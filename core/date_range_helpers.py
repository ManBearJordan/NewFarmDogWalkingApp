from __future__ import annotations
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Australia/Brisbane")

def week_bounds(d: date):
    # Monday start
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=7)
    return start, end

def month_bounds(d: date, offset: int = 0):
    y = d.year + ((d.month - 1 + offset) // 12)
    m = (d.month - 1 + offset) % 12 + 1
    start = date(y, m, 1)
    # next month
    ny = y + (m // 12)
    nm = m % 12 + 1
    if nm == 13:
        nm = 1
        ny = y + 1
    # naive month length calc
    if nm == 1:
        end = date(ny, nm, 1)
    else:
        end = date(ny, nm, 1)
    return start, end

def parse_label(label: str, today: date | None = None):
    """
    Returns (start_datetime, end_datetime) in Australia/Brisbane tz for UI labels.
    """
    if not today:
        today = datetime.now(TZ).date()
    label = (label or "").lower().strip()

    if label in ("this-week", "this_week", "this week"):
        s, e = week_bounds(today)
        return datetime.combine(s, datetime.min.time(), TZ), datetime.combine(e, datetime.min.time(), TZ)
    if label in ("next-week", "next_week", "next week"):
        s, e = week_bounds(today + timedelta(days=7))
        return datetime.combine(s, datetime.min.time(), TZ), datetime.combine(e, datetime.min.time(), TZ)
    if label in ("two-weeks", "two_weeks", "two weeks"):
        s, _ = week_bounds(today)
        e = s + timedelta(days=14)
        return datetime.combine(s, datetime.min.time(), TZ), datetime.combine(e, datetime.min.time(), TZ)
    if label in ("four-weeks", "four_weeks", "four weeks"):
        s, _ = week_bounds(today)
        e = s + timedelta(days=28)
        return datetime.combine(s, datetime.min.time(), TZ), datetime.combine(e, datetime.min.time(), TZ)
    if label in ("this-month", "this_month", "this month"):
        s, e = month_bounds(today, 0)
        return datetime.combine(s, datetime.min.time(), TZ), datetime.combine(e, datetime.min.time(), TZ)
    if label in ("next-month", "next_month", "next month"):
        s, e = month_bounds(today, 1)
        return datetime.combine(s, datetime.min.time(), TZ), datetime.combine(e, datetime.min.time(), TZ)
    if label in ("month-after", "month_after", "month after"):
        s, e = month_bounds(today, 2)
        return datetime.combine(s, datetime.min.time(), TZ), datetime.combine(e, datetime.min.time(), TZ)
    if label in ("next-3-months", "next_3_months", "next 3 months"):
        s, _ = month_bounds(today, 0)
        _, e = month_bounds(today, 3)
        return datetime.combine(s, datetime.min.time(), TZ), datetime.combine(e, datetime.min.time(), TZ)
    # default: this week
    s, e = week_bounds(today)
    return datetime.combine(s, datetime.min.time(), TZ), datetime.combine(e, datetime.min.time(), TZ)