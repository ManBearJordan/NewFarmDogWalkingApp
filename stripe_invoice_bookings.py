from __future__ import annotations
from datetime import datetime, timedelta, timezone
from dateutil import parser as dtparser, tz
import sqlite3
import stripe

# Import unified functions
from unified_booking_helpers import resolve_client_id, get_canonical_service_info, create_booking_with_unified_fields
# Replace ad-hoc normalization with the central helper
from subscription_utils import service_type_from_label

def row_get(row, key, default=None):
    """Helper to safely get values from SQLite rows or dicts"""
    if row is None:
        return default
    if isinstance(row, sqlite3.Row):
        k = key in row.keys()
        return row[key] if k and row[key] is not None else default
    # dict-like
    return row.get(key, default)

def to_naive_iso(s: str) -> str:
    """Convert timezone-aware datetime string to naive ISO format"""
    dt = dtparser.isoparse(s)
    if dt.tzinfo:
        # Convert to local timezone then drop tzinfo
        dt = dt.astimezone(tz.tzlocal()).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def _iso_date(ts):
    # Accepts unix ts (int) or iso string; returns YYYY-MM-DD (UTC)
    if ts is None: return None
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
    try:
        from dateutil import parser as dtparser
        return dtparser.parse(ts).astimezone(timezone.utc).date().isoformat()
    except Exception:
        return None

def promote_subscription_invoices(conn, when: str = "paid", lookback_days: int = 90):
    """
    For each Stripe invoice with a subscription:
      - If invoice.status == `when` (default 'paid'), find matching sub_occurrences
      - Create a booking per occurrence (idempotent via unique index)
      - Link booking to the invoice (stripe_invoice_id + hosted_invoice_url)
    """
    from db import add_booking, update_booking_invoice

    now = datetime.now(timezone.utc)
    since = int((now - timedelta(days=lookback_days)).timestamp())

    it = stripe.Invoice.list(status=when, created={"gte": since}, limit=100,
                             expand=["data.customer", "data.lines"])
    cur = conn.cursor()

    for inv in it.auto_paging_iter():
        sub_id = getattr(inv, "subscription", None)
        if not sub_id:
            continue

        # Resolve client_id from Stripe customer id or email.
        client_id = None
        scid = getattr(getattr(inv, "customer", None), "id", None)
        if scid:
            row = cur.execute("SELECT id FROM clients WHERE stripe_customer_id=?", (scid,)).fetchone()
            client_id = row_get(row, "id")
        if client_id is None:
            email = (getattr(inv, "customer_email", None) or "").lower()
            if email:
                row = cur.execute("SELECT id FROM clients WHERE lower(email)=?", (email,)).fetchone()
                client_id = row_get(row, "id")
        if not client_id:
            continue  # can't create a booking without a client

        # Service label from first line (nickname/description)
        svc = "Subscription"
        try:
            if inv.lines and inv.lines.data:
                l0 = inv.lines.data[0]
                svc = getattr(getattr(l0, "price", None), "nickname", None) or getattr(l0, "description", None) or "Subscription"
        except Exception:
            pass

        # For each line period, map to sub_occurrences for that subscription and date window
        for line in (inv.lines.data if getattr(inv, "lines", None) else []):
            p = getattr(line, "period", None) or {}
            d0 = _iso_date(p.get("start"))
            d1 = _iso_date(p.get("end"))
            if not d0 or not d1:
                continue

            # Pull occurrences in that window
            cur.execute("""
                SELECT so.id, so.start_dt, so.end_dt, so.location, so.dogs,
                       s.client_id, COALESCE(s.service_name, ?) AS service_name
                  FROM sub_occurrences so
                  JOIN subs s ON s.stripe_subscription_id = so.stripe_subscription_id
                 WHERE so.active = 1
                   AND so.stripe_subscription_id = ?
                   AND date(so.start_dt) BETWEEN ? AND ?
                 ORDER BY so.start_dt
            """, (svc, sub_id, d0, d1))

            cols = [c[0] for c in cur.description]
            for r in cur.fetchall():
                oc = dict(zip(cols, r))
                cid = oc.get("client_id") or client_id
                if not cid:
                    continue

                # Try to insert booking (unique index prevents dupes)
                try:
                    bid = add_booking(
                        conn,
                        client_id=cid,
                        service_code=oc["service_name"],
                        start_ts=oc["start_dt"], end_ts=oc["end_dt"],
                        location=oc.get("location") or "",
                        dogs=oc.get("dogs") or 1,
                        price_cents=int(getattr(line, "amount", 0) or 0),
                        notes="Auto-promoted from subscription invoice",
                        stripe_invoice_id=inv.id,
                        invoice_url=getattr(inv, "hosted_invoice_url", None),
                        status=("confirmed" if when == "paid" else "invoiced"),
                    )
                except Exception:
                    # Already exists; look it up and just link it
                    row = cur.execute("""
                        SELECT id FROM bookings
                         WHERE client_id=? AND service_type=? AND start_dt=? AND end_dt=?
                    """, (cid, oc["service_name"], oc["start_dt"], oc["end_dt"])).fetchone()
                    bid = row_get(row, "id")

                if bid:
                    update_booking_invoice(conn, bid, inv.id, getattr(inv, "hosted_invoice_url", None))
                    # (Optional) remember the link on the occurrence
                    cur.execute("UPDATE sub_occurrences SET booking_id=? WHERE id=?", (bid, oc["id"]))
                    conn.commit()

def import_invoice_bookings(conn, lookback_days: int = 90):
    """
    Import bookings from Stripe invoices with metadata.
    More robust implementation that handles timezone conversion and proper client lookup.
    FIXED: Ensures correct client_id, service_type, and service labels are always set.
    Returns count of bookings imported.
    """
    now = datetime.now(timezone.utc)
    since = int((now - timedelta(days=lookback_days)).timestamp())
    
    cur = conn.cursor()
    count = 0
    
    # Process invoices with booking metadata
    for status in ("open", "paid", "draft"):
        it = stripe.Invoice.list(status=status, created={"gte": since}, limit=100,
                                 expand=["data.customer", "data.lines"])
        
        for inv in it.auto_paging_iter():
            # 1) collect metadata (invoice, then fallback to first line item)
            md = getattr(inv, "metadata", {}) or {}
            if ("booking_start" not in md or "booking_end" not in md) and getattr(inv, "lines", None) and inv.lines.data:
                try:
                    li_md = getattr(inv.lines.data[0], "metadata", {}) or {}
                    for k in ("booking_start", "booking_end", "service", "location", "dogs", "dog"):
                        if k in li_md and k not in md:
                            md[k] = li_md[k]
                except Exception:
                    pass
            
            # FIXED: Enhanced service extraction with better fallbacks
            service_label = None
            service_type = None
            
            # Try to get service from metadata first
            if md.get('service'):
                service_label = md['service'].strip()
            if md.get('service_type'):
                service_type = md['service_type'].strip()
            
            # Fallback: extract from line items with better logic
            if not service_label or not service_type:
                for li in inv.lines.data:
                    # Try price nickname first (most descriptive)
                    if hasattr(li, 'price') and hasattr(li.price, 'nickname') and li.price.nickname:
                        if not service_label:
                            service_label = li.price.nickname.strip()
                    
                    # Try line description
                    if hasattr(li, 'description') and li.description:
                        if not service_label:
                            service_label = li.description.strip()
                    
                    # Try price metadata
                    price_md = dict(getattr(li.price, 'metadata', {}) or {})
                    if price_md.get('service_name') and not service_label:
                        service_label = price_md['service_name'].strip()
                    if price_md.get('service_code') and not service_type:
                        service_type = price_md['service_code'].strip()
                    
                    # Try product name as last resort
                    if hasattr(li, 'price') and hasattr(li.price, 'product'):
                        product = li.price.product
                        if hasattr(product, 'name') and product.name and not service_label:
                            service_label = product.name.strip()
                        
                        # Try product metadata
                        if hasattr(product, 'metadata') and product.metadata:
                            prod_md = dict(product.metadata)
                            if prod_md.get('service_name') and not service_label:
                                service_label = prod_md['service_name'].strip()
                            if prod_md.get('service_code') and not service_type:
                                service_type = prod_md['service_code'].strip()
                    
                    # Break if we have both
                    if service_label and service_type:
                        break
            
            # FIXED: Ensure we never use "Subscription" as the final service label
            if not service_label or service_label.lower() == 'subscription':
                service_label = "Dog Walking Service"  # Better default
            
            # FIXED: Derive proper service_type if not found
            if not service_type:
                service_type = service_type_from_label(service_label)
            
            # Skip if we still don't have required booking metadata
            if not md.get('booking_start') or not md.get('booking_end'):
                continue  # skip this invoice
            
            # FIXED: Use unified client resolution
            stripe_customer_id = getattr(getattr(inv, "customer", None), "id", None)
            
            # Must have a valid customer to proceed
            if not stripe_customer_id:
                print(f"Warning: Invoice {inv.id} has no customer - skipping")
                continue
            
            # Use unified resolve_client_id function
            client_id = resolve_client_id(conn, stripe_customer_id)
            
            # Try by email if not found
            if client_id is None:
                email = (getattr(getattr(inv, "customer", None), "email", None) or 
                        getattr(inv, "customer_email", None) or "").lower().strip()
                if email:
                    client_row = cur.execute(
                        "SELECT id FROM clients WHERE LOWER(email)=LOWER(?) LIMIT 1", 
                        (email,)
                    ).fetchone()
                    if client_row:
                        client_id = client_row["id"]
                        # Backfill the Stripe customer ID for future lookups
                        cur.execute("""
                            UPDATE clients 
                            SET stripe_customer_id = COALESCE(stripe_customer_id, ?),
                                stripeCustomerId = COALESCE(stripeCustomerId, ?)
                            WHERE id = ?
                        """, (stripe_customer_id, stripe_customer_id, client_id))
                        conn.commit()
                    else:
                        # Create a new client with proper validation
                        customer = getattr(inv, "customer", None)
                        customer_name = (getattr(customer, "name", None) or email.split('@')[0] or "Unknown Customer").strip()
                        customer_phone = (getattr(customer, "phone", None) or "").strip()
                        billing_address = ""
                        
                        if hasattr(customer, "address") and customer.address:
                            addr = customer.address
                            addr_parts = [
                                getattr(addr, 'line1', ''),
                                getattr(addr, 'line2', ''),
                                getattr(addr, 'city', ''),
                                getattr(addr, 'state', ''),
                                getattr(addr, 'postal_code', '')
                            ]
                            billing_address = " ".join(p for p in addr_parts if p).strip()
                        
                        cur.execute("""
                            INSERT INTO clients (name, email, address, phone, stripe_customer_id, stripeCustomerId)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (customer_name, email, billing_address, customer_phone, stripe_customer_id, stripe_customer_id))
                        conn.commit()
                        client_id = cur.lastrowid
                        print(f"Created new client {client_id} for {email}")
            
            # FIXED: Must have a valid client_id to proceed
            if not client_id:
                print(f"Warning: Could not resolve client for invoice {inv.id} - skipping")
                continue
            
            try:
                # 2) normalize fields with validation
                location = (md.get("location") or "").strip()
                dogs = max(1, int(md.get("dogs") or md.get("dog") or 1))  # Ensure at least 1

                # 3) parse times with error handling
                start_iso = to_naive_iso(md["booking_start"])
                end_iso = to_naive_iso(md["booking_end"])

                # 4) upsert with proper field mapping
                brow = cur.execute("SELECT id FROM bookings WHERE stripe_invoice_id=?",
                                   (inv.id,)).fetchone()
                if brow:
                    cur.execute("""
                        UPDATE bookings
                        SET client_id=?, service=?, service_type=?, service_name=?, 
                            start=?, end=?, start_dt=?, end_dt=?, 
                            location=?, dogs=?, dogs_count=?, status='invoiced'
                        WHERE id=?""",
                        (client_id, service_label, service_type, service_label,
                         start_iso, end_iso, start_iso, end_iso,
                         location, dogs, dogs, brow["id"]))
                    count += 1
                else:
                    cur.execute("""
                        INSERT INTO bookings (
                            client_id, service, service_type, service_name,
                            start, end, start_dt, end_dt,
                            location, dogs, dogs_count, status, stripe_invoice_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'invoiced', ?)""",
                        (client_id, service_label, service_type, service_label,
                         start_iso, end_iso, start_iso, end_iso,
                         location, dogs, dogs, inv.id))
                    count += 1
                conn.commit()
                
            except Exception as e:
                # Log error but continue processing
                print(f"Error processing invoice {inv.id}: {e}")
                continue
    
    return count

def list_invoice_bookings(days_ahead: int = 14, lookback_days: int = 90):
    now = datetime.now(timezone.utc)
    end_window = now + timedelta(days=days_ahead)
    since = int((now - timedelta(days=lookback_days)).timestamp())
    out = []
    for status in ("open", "paid", "draft"):
        it = stripe.Invoice.list(status=status, created={"gte": since}, limit=100,
                                 expand=["data.customer", "data.lines"])
        for inv in it.auto_paging_iter():
            md = getattr(inv, "metadata", {}) or {}

            # Fallback: first line item metadata
            if ("booking_start" not in md or "booking_end" not in md) and getattr(inv, "lines", None) and inv.lines.data:
                try:
                    li_md = getattr(inv.lines.data[0], "metadata", {}) or {}
                    for k in ("booking_start", "booking_end", "service", "location", "dogs", "dog"):
                        if k in li_md and k not in md:
                            md[k] = li_md[k]
                except Exception:
                    pass

            if "booking_start" not in md or "booking_end" not in md:
                continue  # skip this invoice

            try:
                # Use the timezone-aware datetime conversion
                start_naive = to_naive_iso(md["booking_start"])
                end_naive = to_naive_iso(md["booking_end"])
                start = dtparser.parse(start_naive)
                end = dtparser.parse(end_naive)
            except Exception:
                continue
            if end < now or start > end_window:
                continue
            svc = md.get("service") or (inv.lines.data[0].description
                   if getattr(inv, "lines", None) and inv.lines.data else "Service")
            try: dogs = int(md.get("dogs") or 1)
            except Exception: dogs = 1
            location = md.get("location") or ""
            cust = getattr(inv, "customer", None)
            cust_email = getattr(cust, "email", None) or getattr(inv, "customer_email", None) or ""
            cust_name  = getattr(cust, "name",  None) or ""
            out.append({
                "stripe_invoice_id": inv.id, "status": inv.status,
                "client_email": cust_email, "client_name": cust_name,
                "service": svc, "start_dt": start.isoformat(), "end_dt": end.isoformat(),
                "dogs": dogs, "location": location,
            })
    return out
