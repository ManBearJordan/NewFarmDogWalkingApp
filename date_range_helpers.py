from datetime import date, datetime, time, timedelta
import calendar

def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())  # Monday-start

def _month_bounds(d: date):
    start = d.replace(day=1)
    _, days = calendar.monthrange(start.year, start.month)
    end = start + timedelta(days=days)  # exclusive
    return start, end

def resolve_range(label: str, today: date | None = None):
    if not today:
        today = date.today()
    if label == "This week":
        s = _week_start(today); e = s + timedelta(days=7)
    elif label == "Next week":
        s = _week_start(today) + timedelta(days=7); e = s + timedelta(days=7)
    elif label == "Two weeks (this+next)":
        s = _week_start(today); e = s + timedelta(days=14)
    elif label == "Four weeks (this+3)":
        s = _week_start(today); e = s + timedelta(days=28)
    elif label == "This month":
        s, e = _month_bounds(today)
    elif label == "Next month":
        s0 = today.replace(day=1)
        nm = (s0.month % 12) + 1; ny = s0.year + (1 if s0.month == 12 else 0)
        s = date(ny, nm, 1); _, days = calendar.monthrange(ny, nm); e = s + timedelta(days=days)
    elif label == "Month after":
        s0 = today.replace(day=1)
        nm = ((s0.month + 1) % 12) + 1; ny = s0.year + (1 if s0.month >= 11 else 0)
        s = date(ny, nm, 1); _, days = calendar.monthrange(ny, nm); e = s + timedelta(days=days)
    else:  # "Next 3 months"
        s, _ = _month_bounds(today)
        # end = first day after three full months
        m1 = (s.month % 12) + 1; y1 = s.year + (1 if s.month == 12 else 0)
        m2 = (m1 % 12) + 1;     y2 = y1 + (1 if m1 == 12 else 0)
        m3 = (m2 % 12) + 1;     y3 = y2 + (1 if m2 == 12 else 0)
        e = date(y3, m3, 1)
    return datetime.combine(s, time.min), datetime.combine(e, time.min)
