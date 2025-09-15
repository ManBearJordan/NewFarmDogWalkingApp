# reports.py
from __future__ import annotations
from datetime import datetime, timedelta
from collections import defaultdict

def run_sheet_for_day(conn, day_dt: datetime) -> list[dict]:
    """Return bookings for day grouped by hour start."""
    start = day_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    cur = conn.cursor()
    cur.execute("""
      SELECT b.id, c.name AS client, COALESCE(b.service, b.service_type) AS service, 
             b.start_dt, b.end_dt, b.location, COALESCE(b.dogs_count,b.dogs,1) AS dogs
      FROM bookings b LEFT JOIN clients c ON c.id=b.client_id
      WHERE b.start_dt >= ? AND b.start_dt < ? AND COALESCE(b.deleted,0)=0
      ORDER BY b.start_dt
    """, (start.isoformat(), end.isoformat()))
    cols = [c[0] for c in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    groups = defaultdict(list)
    for r in rows:
        try:
            start_dt = datetime.fromisoformat(r["start_dt"])
            key = start_dt.strftime("%H:%M")
        except Exception:
            key = "00:00"
        groups[key].append(r)
    out = []
    for k in sorted(groups.keys()):
        out.append({"slot": k, "items": groups[k]})
    return out

def outstanding_invoices(stripe) -> list[dict]:
    out = []
    for st in ("open","uncollectible"):
        page = stripe.Invoice.list(status=st, limit=100)
        for inv in page.auto_paging_iter():
            out.append({
                "id": inv.id,
                "status": inv.status,
                "customer": inv.customer_email or inv.customer_name,
                "amount_aud": inv.amount_due/100.0,
                "url": getattr(inv, "hosted_invoice_url", None),
                "created": inv.created
            })
    out.sort(key=lambda x: x["created"])
    return out

def revenue_summary(conn, start_dt: str, end_dt: str) -> list[dict]:
    """
    Sums from booking_items if present, else bookings.price_cents.
    """
    cur = conn.cursor()
    cur.execute("""
      SELECT COALESCE(b.service, b.service_type) AS service,
             COALESCE( (SELECT SUM(qty*unit_amount_cents) FROM booking_items bi WHERE bi.booking_id=b.id),
                       COALESCE(b.price_cents,0)
             ) AS cents
      FROM bookings b
      WHERE b.start_dt >= ? AND b.start_dt < ? AND COALESCE(b.deleted,0)=0
    """, (start_dt, end_dt))
    rows = {}
    for svc, cents in cur.fetchall():
        rows[svc] = rows.get(svc, 0) + int(cents or 0)
    return [{"service": k, "amount_aud": v/100.0} for k,v in sorted(rows.items())]
