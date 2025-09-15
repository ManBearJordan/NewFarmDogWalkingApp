
import os, json, datetime
from typing import Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/calendar"]

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "google_token.json")

def get_service(creds_path: Optional[str] = None):
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_path or not os.path.exists(creds_path):
                raise RuntimeError("Pick your Google OAuth client file (credentials.json).")
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    service = build("calendar", "v3", credentials=creds)
    return service

def ensure_calendar(service, summary="New Farm Dog Walking"):
    cals = service.calendarList().list().execute()
    for item in cals.get("items", []):
        if item.get("summary") == summary:
            return item["id"]
    # create
    cal = service.calendars().insert(body={"summary": summary, "timeZone": "Australia/Brisbane"}).execute()
    return cal["id"]

def upsert_event(service, calendar_id, booking):
    # booking: dict with id, client_name, service_type, start_dt, end_dt, location, notes
    eid = f"nfdw-booking-{booking['id']}"
    body = {
        "id": eid[:1024],
        "summary": f"{booking['service_type']} — {booking['client_name']}",
        "location": booking.get("location") or "",
        "description": booking.get("notes") or "",
        "start": {"dateTime": booking["start_dt"]},
        "end": {"dateTime": booking["end_dt"]},
    }
    try:
        service.events().update(calendarId=calendar_id, eventId=eid, body=body).execute()
    except Exception:
        service.events().insert(calendarId=calendar_id, body=body).execute()

def upsert_event_enhanced(service, calendar_id: str, booking: dict) -> str:
    """
    booking: {id, title, start_ts, end_ts, location, stripe_invoice_id}
    Returns eventId. Uses private extendedProperties to link.
    """
    from datetime import timezone
    props = {"booking_id": str(booking["id"])}
    if booking.get("stripe_invoice_id"):
        props["stripe_invoice_id"] = booking["stripe_invoice_id"]

    body = {
        "summary": booking["title"],
        "location": booking.get("location") or "",
        "start": {"dateTime": datetime.datetime.fromtimestamp(booking["start_ts"], tz=timezone.utc).isoformat()},
        "end":   {"dateTime": datetime.datetime.fromtimestamp(booking["end_ts"], tz=timezone.utc).isoformat()},
        "extendedProperties": {"private": props},
    }
    event_id = booking.get("google_event_id")
    if event_id:
        evt = service.events().patch(calendarId=calendar_id, eventId=event_id, body=body).execute()
    else:
        evt = service.events().insert(calendarId=calendar_id, body=body).execute()
    return evt["id"]

def sync_all_enhanced(service, calendar_id: str, rows: list[dict]) -> int:
    n = 0
    for r in rows:
        try:
            eid = upsert_event_enhanced(service, calendar_id, r)
            n += 1
        except Exception:
            pass
    return n

def sync_all_bookings(conn, creds_path: Optional[str] = None, calendar_summary="New Farm Dog Walking"):
    service = get_service(creds_path)
    cal_id = ensure_calendar(service, calendar_summary)
    rows = conn.execute("""
        SELECT b.id, c.name as client_name, b.service_type, b.start_dt, b.end_dt, b.location, b.notes
        FROM bookings b JOIN clients c ON b.client_id=c.id
    """).fetchall()
    for r in rows:
        upsert_event(service, cal_id, dict(r))
    return len(rows)

def ensure_service(creds_path: str):
    from datetime import timezone
    creds = Credentials.from_authorized_user_file(creds_path, scopes=["https://www.googleapis.com/auth/calendar"])
    return build("calendar", "v3", credentials=creds)
