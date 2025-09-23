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

def parse_label(label: str, today: date | None = None, start_param: str | None = None, end_param: str | None = None):
    """
    Returns (start_datetime, end_datetime) in Australia/Brisbane tz for UI labels.
    For 'custom' label, uses start_param and end_param dates.
    """
    if not today:
        today = datetime.now(TZ).date()
    label = (label or "").lower().strip()

    # Handle custom range using start_param and end_param
    if label == "custom" and start_param and end_param:
        try:
            start_date = datetime.strptime(start_param, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_param, "%Y-%m-%d").date()
            # End date should be inclusive, so add 1 day for the range
            end_date = end_date + timedelta(days=1)
            return datetime.combine(start_date, datetime.min.time(), TZ), datetime.combine(end_date, datetime.min.time(), TZ)
        except (ValueError, TypeError):
            # Fall back to default range if custom dates are invalid
            pass

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


def list_presets():
    """
    Return list of (value, label) tuples for all date range presets, including custom.
    """
    return [
        ("this-week", "This week"),
        ("next-week", "Next week"),
        ("two-weeks", "Two weeks"),
        ("four-weeks", "Four weeks"),
        ("this-month", "This month"),
        ("next-month", "Next month"),
        ("month-after", "Month after"),
        ("next-3-months", "Next 3 months"),
        ("custom", "Custom range"),
    ]