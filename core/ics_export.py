from __future__ import annotations
from typing import Iterable
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib

from django.utils import timezone

TZ = ZoneInfo("Australia/Brisbane")

def _ical_escape(text: str) -> str:
    """
    RFC 5545 escaping for TEXT: backslash, comma, semicolon, and newlines.
    """
    text = (text or "")
    text = text.replace("\\", "\\\\")
    text = text.replace(",", "\\,")
    text = text.replace(";", "\\;")
    text = text.replace("\r\n", "\\n").replace("\n", "\\n")
    return text

def _fmt_dt(dt: datetime) -> str:
    """
    FORMAT: local time with TZID=Australia/Brisbane, floating avoided.
    We'll output VALUE=DATE-TIME with TZID on DTSTART/DTEND lines.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    dt = dt.astimezone(TZ)
    return dt.strftime("%Y%m%dT%H%M%S")

def _uid_for(booking) -> str:
    """
    Stable-ish UID per booking id + start time to avoid collisions across environments.
    """
    raw = f"booking-{booking.id}-{int(booking.start_dt.timestamp())}"
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    # Use a domain-like suffix to make calendar apps happy.
    return f"{h}@newfarmdogwalking"

def bookings_to_ics(qs: Iterable, *, alarm: bool = False, alarm_minutes: int | str = 5) -> str:
    """
    Convert bookings to a single iCalendar string.
    - Excludes cancelled/voided/deleted rows at the caller (view already filters).
    - Adds a display VALARM if alarm=True with configurable minutes before (default 5).
    - alarm_minutes: falls back to 5 if invalid input, clamps to min 1 minute.
    """
    # Handle alarm_minutes edge cases
    try:
        alarm_min = int(alarm_minutes)
        if alarm_min < 1:
            alarm_min = 1  # Clamp to minimum 1 minute
    except (ValueError, TypeError):
        alarm_min = 5  # Fall back to 5 minutes for invalid input
    now = timezone.now().astimezone(TZ)
    dtstamp = now.strftime("%Y%m%dT%H%M%S")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//NewFarmDogWalking//Bookings//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for b in qs:
        start = _fmt_dt(b.start_dt)
        end = _fmt_dt(b.end_dt)
        summary = b.service_label or b.service_name or b.service_code or "Service"
        desc_parts = []
        if getattr(b, "notes", ""):
            desc_parts.append(str(b.notes))
        # include client for clarity in personal calendars
        if getattr(b, "client", None):
            desc_parts.append(f"Client: {getattr(b.client, 'name', '')}")
        description = _ical_escape("\n".join(p for p in desc_parts if p))
        location = _ical_escape(getattr(b, "location", "") or "")

        lines += [
            "BEGIN:VEVENT",
            f"UID:{_uid_for(b)}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART;TZID=Australia/Brisbane:{start}",
            f"DTEND;TZID=Australia/Brisbane:{end}",
            f"SUMMARY:{_ical_escape(summary)}",
            f"DESCRIPTION:{description}",
            f"LOCATION:{location}",
        ]
        if alarm:
            lines += [
                "BEGIN:VALARM",
                f"TRIGGER:-PT{alarm_min}M",
                "ACTION:DISPLAY",
                "DESCRIPTION:Reminder",
                "END:VALARM",
            ]
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"