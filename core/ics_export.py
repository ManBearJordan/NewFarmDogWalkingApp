from __future__ import annotations
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Iterable

def _fmt(dt):
    # ICS in local tz with TZID
    return dt.strftime("%Y%m%dT%H%M%S")

def bookings_to_ics(bookings: Iterable, tz_str: str = "Australia/Brisbane") -> str:
    """
    Minimal ICS builder (no external deps). Expects bookings with:
    start_dt, end_dt (aware), service_label/name, client, location, notes, id
    """
    tz = ZoneInfo(tz_str)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//NewFarmDogWalking//Calendar//EN",
        f"X-WR-TIMEZONE:{tz_str}",
    ]
    for b in bookings:
        title = b.service_label or b.service_name or b.service_code or "Service"
        desc = f"Client: {b.client.name}\\nService: {title}\\nNotes: {b.notes or ''}"
        uid = f"booking-{b.id}@newfarmdogwalking"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART;TZID={tz_str}:{_fmt(b.start_dt.astimezone(tz))}",
            f"DTEND;TZID={tz_str}:{_fmt(b.end_dt.astimezone(tz))}",
            f"SUMMARY:{title}",
            f"LOCATION:{(b.location or '').replace(',', ' ')}",
            f"DESCRIPTION:{desc}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)