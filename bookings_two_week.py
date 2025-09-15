# bookings_two_week.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Iterable, Tuple, List, Dict

def week_window(which: str = "this") -> Tuple[datetime, datetime]:
    """Return [start, end) datetimes for this or next week (Mon..Mon) in UTC."""
    now = datetime.now(timezone.utc)
    monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    if which == "next":
        monday = monday + timedelta(days=7)
    start = monday
    end = monday + timedelta(days=7)
    return start, end

def _ts(dt_str: str) -> int:
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return 0

def list_db_bookings(conn, start: datetime, end: datetime) -> List[Dict]:
    """Return DB bookings within [start,end)."""
    cur = conn.cursor()
    # Use datetime() function for more robust comparison as suggested in the fix
    cur.execute(
        """
        SELECT
            b.id, b.client_id, c.name AS client_name,
            COALESCE(b.service, b.service_type) AS service,
            b.start_dt, b.end_dt,
            COALESCE(b.dogs_count, 1) AS dogs,
            b.location, b.status,
            b.stripe_invoice_id, b.invoice_url,
            COALESCE(b.google_event_id, '') AS google_event_id,
            COALESCE(b.notes, '') AS notes,
            COALESCE(b.price_cents, 0) AS price_cents
        FROM bookings b
        LEFT JOIN clients c ON c.id=b.client_id
        WHERE COALESCE(b.deleted,0)=0
          AND datetime(b.start_dt) >= datetime(?)
          AND datetime(b.start_dt) < datetime(?)
        ORDER BY b.start_dt ASC
        """,
        (start.isoformat(), end.isoformat()),
    )
    rows = []
    for r in cur.fetchall():
        row = dict(zip([c[0] for c in cur.description], r))
        row["start_ts"] = _ts(row.get("start_dt", ""))
        row["end_ts"] = _ts(row.get("end_dt", ""))
        row["source"] = "db"
        rows.append(row)
    return rows

def list_subscription_holds(conn, start: datetime, end: datetime) -> List[Dict]:
    """Return subscription holds from sub_occurrences within [start,end)."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT so.start_dt, so.end_dt, so.dogs, so.location, so.notes,
               so.stripe_subscription_id
        FROM sub_occurrences so
        WHERE so.active=1
          AND so.start_dt >= ? AND so.start_dt < ?
        ORDER BY so.start_dt
        """,
        (start.isoformat(), end.isoformat()),
    )
    rows = []
    cols = [d[0] for d in cur.description]
    for r in cur.fetchall():
        row = dict(zip(cols, r))
        rows.append({
            "id": f"sub-{row.get('stripe_subscription_id', 'unknown')}",
            "source": "sub",
            "client_id": None,
            "client_name": "Subscription",
            "service": "Subscription",
            "start_dt": row["start_dt"],
            "end_dt": row["end_dt"],
            "start_ts": _ts(row.get("start_dt", "")),
            "end_ts": _ts(row.get("end_dt", "")),
            "dogs": row.get("dogs") or 1,
            "location": row.get("location") or "",
            "status": "hold",
            "stripe_invoice_id": None,
            "invoice_url": None,
            "google_event_id": None,
        })
    return rows

def list_invoice_bookings(start: datetime, end: datetime) -> List[Dict]:
    """Return invoice-derived bookings in [start,end) using stripe_invoice_bookings helper."""
    try:
        from secrets_config import get_stripe_key
        import stripe
        stripe.api_key = get_stripe_key()
        from stripe_invoice_bookings import list_invoice_bookings as _lib
    except Exception:
        # Fallback: no Stripe configured
        return []
    items = _lib(days_ahead=max(1, (end - start).days), lookback_days=90)
    out: List[Dict] = []
    for it in items:
        st = _ts(it.get("start_dt", it.get("start") or ""))
        if st >= int(start.timestamp()) and st < int(end.timestamp()):
            row = {
                "id": it.get("stripe_invoice_id") or it.get("id") or f"inv-{st}",
                "source": "invoice",
                "client_id": None,
                "client_name": it.get("client_name") or "Stripe customer",
                "service": it.get("service") or "Service",
                "start_ts": st,
                "end_ts": _ts(it.get("end_dt", it.get("end") or "")),
                "dogs": int(it.get("dogs") or 1),
                "location": it.get("location") or "",
                "status": it.get("status") or "open",
                "stripe_invoice_id": it.get("stripe_invoice_id"),
                "invoice_url": it.get("invoice_url"),
                "google_event_id": None,
            }
            out.append(row)
    return out

def signature(row: Dict) -> tuple:
    return (
        row.get("stripe_invoice_id") or "",
        row.get("client_id") or row.get("client_name") or "",
        row.get("service") or "",
        row.get("start_ts") or 0,
        row.get("end_ts") or 0,
    )

def merge_dedupe(*sources: Iterable[Dict]) -> List[Dict]:
    out: Dict[tuple, Dict] = {}
    for src in sources:
        for r in src:
            key = signature(r)
            if key in out:
                # prefer invoice > db > sub
                def _rank(s): return {"invoice":3, "db":2, "sub":1}.get((s or "db"), 2)
                if _rank(r.get("source")) > _rank(out[key].get("source")):
                    out[key] = r
            else:
                out[key] = r
    rows = list(out.values())
    rows.sort(key=lambda x: (x.get("start_ts", 0), x.get("client_name", "")))
    return rows
