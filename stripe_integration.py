# stripe_integration.py

import os, webbrowser
import stripe
from stripe.error import AuthenticationError
from datetime import datetime, timezone, timedelta
from stripe_key_manager import get_stripe_key, prompt_for_stripe_key, set_stripe_key

def ensure_stripe_key():
    # Always called on launch - but skip interactive prompts during tests
    import sys
    is_test = 'pytest' in sys.modules or 'unittest' in sys.modules
    
    key = get_stripe_key()
    if not key and not is_test:
        # If no key exists at all, prompt for it (but not during tests)
        key = prompt_for_stripe_key()
        if key:
            set_stripe_key(key)
    
    if key:  # Only proceed if we have a key
        stripe.api_key = key

        # Test the key by making a lightweight API call
        try:
            stripe.Customer.list(limit=1)
        except AuthenticationError:
            # Key is invalid/expired, prompt for a new one
            if not is_test:
                new_key = prompt_for_stripe_key()
                if new_key:
                    set_stripe_key(new_key)
                    stripe.api_key = new_key
                    # Optionally retry the call here, or ask user to restart
        except Exception as e:
            # Handle other errors (like network/SSL issues) by not treating them as auth errors
            if "authentication" in str(e).lower() or "invalid" in str(e).lower():
                # Treat as authentication error
                if not is_test:
                    new_key = prompt_for_stripe_key()
                    if new_key:
                        set_stripe_key(new_key)
                        stripe.api_key = new_key
            else:
                # Network or other error - don't prompt for new key, just log it
                print(f"Warning: Unable to validate Stripe key due to network error: {e}")
                pass
    else:
        # No key available, set empty api key
        stripe.api_key = ""

# Call ensure_stripe_key() at app launch
ensure_stripe_key()

# -------------------------
# Key management utilities
# -------------------------
def refresh_stripe_api_key():
    """Refresh the Stripe API key from secure storage"""
    from stripe_key_manager import get_stripe_key
    new_key = get_stripe_key()
    stripe.api_key = new_key
    return new_key

def get_current_stripe_key():
    """Get the currently configured Stripe API key"""
    return getattr(stripe, "api_key", "")

# -------------------------
# Small utilities
# -------------------------
def calculate_weekly_quantity(price, qty):
    """
    Given a Stripe price object and subscription quantity, calculate the weekly quantity.
    Handles different billing intervals and interval counts.
    """
    # given a Stripe price `price` and subscription quantity `qty`:
    rec = price.get("recurring") if isinstance(price, dict) else getattr(price, "recurring", None)
    interval = rec.get("interval") if isinstance(rec, dict) else getattr(rec, "interval", None)
    interval_count = rec.get("interval_count", 1) if isinstance(rec, dict) else getattr(rec, "interval_count", 1)

    weekly_qty = 0
    if interval == "week" and interval_count:
        weekly_qty += qty / int(interval_count)   # e.g. fortnightly qty 2 -> 1 per week
    
    return weekly_qty

def _api():
    # Stripe module with key already set above
    if not getattr(stripe, "api_key", None):
        raise RuntimeError("Stripe API key missing.")
    return stripe

def open_url(url: str):
    try:
        webbrowser.open(url)
    except Exception:
        pass

def stripe_mode():
    key = (getattr(stripe, "api_key", "") or "").strip()
    return "test" if key.startswith("sk_test") else "live"

def open_in_stripe(kind: str, obj_id: str, mode: str | None = None):
    base = "https://dashboard.stripe.com"
    mode = stripe_mode() if mode is None else mode
    if mode == "test":
        base += "/test"
    if kind == "invoice":
        url = f"{base}/invoices/{obj_id}"
    elif kind == "customer":
        url = f"{base}/customers/{obj_id}"
    else:
        url = base
    open_url(url)

# -------------------------
# Booking → Invoice helpers
# -------------------------
def _booking_metadata_from_db(conn, booking_id: int) -> dict:
    cur = conn.cursor()
    row = cur.execute("""
        SELECT
            COALESCE(b.start, b.start_dt)           AS start_iso,
            COALESCE(b.end,   b.end_dt)             AS end_iso,
            COALESCE(b.service, b.service_type, '') AS service_name,
            COALESCE(b.service_type, b.service, '') AS service_code,
            COALESCE(b.location, '')                AS location,
            COALESCE(b.dogs, b.dogs_count, 1)       AS dogs
        FROM bookings b
        WHERE b.id = ?
    """, (booking_id,)).fetchone()
    if not row:
        return {}
    return {
        "booking_id":     str(booking_id),
        "booking_start":  row["start_iso"] or "",
        "booking_end":    row["end_iso"] or "",
        "service":        row["service_name"] or "",
        "service_type":   row["service_code"] or "",
        "location":       row["location"] or "",
        "dogs":           str(row["dogs"] or 1),
    }

def ensure_customer(email: str, name: str = "", phone: str = "") -> str:
    """
    Return a Stripe customer id for the given email.
    Creates a new customer if none exists.
    """
    if not email:
        raise ValueError("Customer email required to create Stripe invoices.")
    try:
        res = stripe.Customer.search(query=f"email:'{email}'", limit=1)
        if res and res.data:
            return res.data[0].id
    except Exception:
        lst = stripe.Customer.list(email=email, limit=1)
        if lst and lst.data:
            return lst.data[0].id
    cust = stripe.Customer.create(email=email, name=name or "", phone=phone or "")
    return cust.id

def create_draft_invoice_for_booking(
    customer_id: str,
    price_id: str,
    quantity: int,
    metadata: dict,
    description: str | None = None,
    days_until_due: int = 7,
):
    """
    Creates a sendable draft invoice for a one-time booking.
    - Adds an invoice item for the selected Price (quantity = number of dogs or units)
    - Creates the Invoice (send_invoice mode), finalizes it, and returns URL.
    """
    # Attach metadata to BOTH the line item and the invoice
    stripe.InvoiceItem.create(
        customer=customer_id,
        price=price_id,
        quantity=max(1, int(quantity or 1)),
        metadata=metadata or {},
        description=description or (metadata or {}).get("service_code", "Booking"),
    )

    inv = stripe.Invoice.create(
        customer=customer_id,
        collection_method="send_invoice",
        days_until_due=days_until_due,
        metadata=metadata or {},
        auto_advance=False,  # we finalize explicitly
    )

    inv = stripe.Invoice.finalize_invoice(inv.id)
    return {
        "id": inv.id,
        "url": getattr(inv, "hosted_invoice_url", None),
        "status": inv.status,
        "number": getattr(inv, "number", None),
    }

def create_invoice_with_item(
    customer_id: str,
    price_id: str,
    quantity: int,
    metadata: dict,
    finalize: bool = False,
):
    """
    Create a draft invoice with one price line (quantity=quantity).
    Metadata is attached to both the line and the invoice.
    If finalize=True, the invoice is finalized (so hosted_invoice_url is available).
    Returns the invoice object.
    """
    inv = stripe.Invoice.create(
        customer=customer_id,
        auto_advance=False,
        collection_method="send_invoice",
        days_until_due=14,
        metadata=metadata or {},
    )
    stripe.InvoiceItem.create(
        customer=customer_id,
        invoice=inv.id,
        price=price_id,
        quantity=max(1, int(quantity or 1)),
        metadata=metadata or {},
    )
    if finalize:
        inv = stripe.Invoice.finalize_invoice(inv.id)
    else:
        inv = stripe.Invoice.retrieve(inv.id)
    return inv

def create_draft_invoice_with_items(*, customer_id: str, items: list[dict], invoice_metadata: dict) -> dict:
    """
    items: [{stripe_price_id, qty, service_name}]
    Returns {invoice_id, hosted_invoice_url, status}
    """
    inv = stripe.Invoice.create(
        customer=customer_id,
        auto_advance=False,
        collection_method="send_invoice",
        days_until_due=14,
        metadata=invoice_metadata or {}
    )
    for it in items:
        stripe.InvoiceItem.create(
            customer=customer_id,
            invoice=inv.id,
            price=it["stripe_price_id"],
            quantity=int(it.get("qty", 1)),
            metadata={"service_name": it.get("service_name", "")}
        )
    inv = stripe.Invoice.finalize_invoice(inv.id)
    return {
        "invoice_id": inv.id,
        "hosted_invoice_url": getattr(inv, "hosted_invoice_url", None),
        "status": inv.status
    }

# -------------------------
# Invoice creation for bookings (Fix C)
# -------------------------
def ensure_draft_invoice_for_booking(conn, booking_id):
    """
    Finds or creates a draft invoice for the given booking.
    Returns the Stripe invoice object.
    """
    cur = conn.cursor()
    row = cur.execute("""
        SELECT b.id, b.client_id, b.stripe_invoice_id, b.invoice_url,
               c.stripe_customer_id
          FROM bookings b LEFT JOIN clients c ON c.id=b.client_id
         WHERE b.id=?
    """, (booking_id,)).fetchone()
    if not row: 
        raise RuntimeError("Booking not found")

    # ... fetch client + existing invoice ...
    md = _booking_metadata_from_db(conn, booking_id)

    if row["stripe_invoice_id"]:
        inv = stripe.Invoice.retrieve(row["stripe_invoice_id"])
        # Optional: ensure metadata is present even for older invoices
        if md:
            try: 
                stripe.Invoice.modify(inv.id, metadata=md)
            except Exception: 
                pass
        return inv

    if not row["stripe_customer_id"]:
        raise RuntimeError("Client not linked to a Stripe customer")

    inv = stripe.Invoice.create(
        customer=row["stripe_customer_id"],
        collection_method="send_invoice",
        days_until_due=14,    # ✅ default so creation never errors; you can change in Edit
        auto_advance=False,   # keep as draft
        metadata=md,          # <-- add this
    )
    conn.execute(
        "UPDATE bookings SET stripe_invoice_id=?, invoice_url=? WHERE id=?",
        (inv.id, getattr(inv, "hosted_invoice_url", None), booking_id)
    )
    conn.commit()
    return inv

def push_invoice_items_from_booking(conn, booking_id, invoice_id):
    """
    Adds invoice items from booking with idempotency key to prevent duplicates.
    Also applies credit as specified in task requirements.
    """
    from db import get_client_credit, use_client_credit
    
    cur = conn.cursor()
    
    # Get customer ID and client ID for the booking
    row = cur.execute("""
        SELECT b.id, b.client_id, b.service_type, b.price_cents, c.stripe_customer_id, c.credit_cents
        FROM bookings b JOIN clients c ON c.id=b.client_id
        WHERE b.id=?
    """, (booking_id,)).fetchone()
    
    if not row or not row["stripe_customer_id"]:
        raise RuntimeError("Client not linked to a Stripe customer")
    
    customer_id = row["stripe_customer_id"]
    client_id = row["client_id"]
    price_cents = row["price_cents"] or 0
    md = _booking_metadata_from_db(conn, booking_id)
    
    # Apply credit logic as specified in task requirements
    credit_used = use_client_credit(conn, client_id, price_cents)
    amount_due = price_cents - credit_used
    
    # Check for explicit line items first
    items = cur.execute("""
        SELECT stripe_price_id, qty, service_name
        FROM booking_items
        WHERE booking_id=?
    """, (booking_id,)).fetchall()
    
    if items:
        # Use explicit line items with idempotency
        for item in items:
            if amount_due > 0:
                idempotency_key = f"invitem:{invoice_id}:{booking_id}:{item['stripe_price_id']}"
                stripe.InvoiceItem.create(
                    customer=customer_id,
                    invoice=invoice_id,
                    price=item["stripe_price_id"],
                    quantity=int(item["qty"] or 1),
                    idempotency_key=idempotency_key,
                    metadata=md
                )
    else:
        # Fallback to booking price/service
        booking_row = cur.execute("""
            SELECT stripe_price_id, service, price_cents, service_type
            FROM bookings WHERE id=?
        """, (booking_id,)).fetchone()
        
        if amount_due > 0:
            if booking_row and booking_row["stripe_price_id"]:
                # Use Stripe Price ID
                idempotency_key = f"invitem:{invoice_id}:{booking_id}"
                stripe.InvoiceItem.create(
                    customer=customer_id,
                    invoice=invoice_id,
                    price=booking_row["stripe_price_id"],
                    quantity=1,
                    idempotency_key=idempotency_key,
                    metadata=md
                )
            elif booking_row and amount_due > 0:
                # Use one-off amount (reduced by credit)
                idempotency_key = f"invitem:{invoice_id}:{booking_id}"
                stripe.InvoiceItem.create(
                    customer=customer_id,
                    invoice=invoice_id,
                    amount=int(amount_due),
                    currency="aud",
                    description=booking_row["service"] or booking_row["service_type"] or "Service",
                    idempotency_key=idempotency_key,
                    metadata=md
                )
    
    # Add credit line item if credit was used
    if credit_used > 0:
        credit_idempotency_key = f"credit:{invoice_id}:{booking_id}"
        stripe.InvoiceItem.create(
            customer=customer_id,
            invoice=invoice_id,
            amount=-credit_used,
            currency="aud",
            description="Credit applied",
            idempotency_key=credit_idempotency_key,
            metadata=md
        )

def open_invoice_smart(invoice_id: str):
    """Open the right page for this invoice:
       - draft  -> Dashboard Edit screen
       - open/paid/void/uncollectible -> Dashboard View screen
    Also opens the hosted (customer) link if finalized and available.
    """
    inv = stripe.Invoice.retrieve(invoice_id)

    base = "https://dashboard.stripe.com"
    if getattr(stripe, "api_key", "").startswith("sk_test_"):
        base += "/test"

    status = getattr(inv, "status", None)  # 'draft','open','paid','void','uncollectible'
    if status == "draft":
        # Directly into the edit UI
        url = f"{base}/invoices/{invoice_id}/edit"
        webbrowser.open(url)
    else:
        # Finalized or otherwise not editable -> open the dashboard details page
        url = f"{base}/invoices/{invoice_id}"
        webbrowser.open(url)
        # Optional: also open the customer-facing hosted link if present
        hosted = getattr(inv, "hosted_invoice_url", None)
        if hosted:
            webbrowser.open(hosted)

def open_invoice_in_dashboard(invoice_id):
    """
    Opens the invoice edit page in Stripe Dashboard.
    Detects test vs live mode and adjusts URL accordingly.
    """
    base = "https://dashboard.stripe.com"
    # open test dashboard if using a test key
    try:
        if stripe.api_key and stripe.api_key.startswith("sk_test_"):
            base += "/test"
    except Exception:
        pass
    import webbrowser
    webbrowser.open(f"{base}/invoices/{invoice_id}")

def finalize_and_url(invoice_id):
    inv = stripe.Invoice.finalize_invoice(invoice_id, expand=["payment_intent"])
    return getattr(inv, "hosted_invoice_url", None) or getattr(inv, "invoice_pdf", None)

def finalize_and_get_url(invoice_id):
    """
    Finalizes an invoice and returns the hosted URL.
    """
    inv = stripe.Invoice.finalize_invoice(invoice_id, expand=["payment_intent"])
    # If you prefer to keep draft: skip finalize and just return hosted URL (Stripe shows draft preview).
    return getattr(inv, "hosted_invoice_url", None) or getattr(inv, "invoice_pdf", None)

def _open_invoice_in_dashboard(invoice_id):
    """
    Opens the invoice edit page in Stripe Dashboard.
    Detects test vs live mode and adjusts URL accordingly.
    """
    base = "https://dashboard.stripe.com"
    # open test dashboard if using a test key
    try:
        import stripe
        if stripe.api_key and stripe.api_key.startswith("sk_test_"):
            base += "/test"
    except Exception:
        pass
    webbrowser.open(f"{base}/invoices/{invoice_id}/edit")  # <-- auto-opens to edit page

def _create_invoice_and_open(conn, booking_id, line_items=None):
    """
    Creates a draft invoice for the booking and automatically opens it in the Stripe dashboard.
    line_items: optional list of {'price_id': 'price_x', 'quantity': 1}
    """
    inv = ensure_draft_invoice_for_booking(conn, booking_id)
    push_invoice_items_from_booking(conn, booking_id, inv.id)
    _open_invoice_in_dashboard(inv.id)  # <-- open automatically
    return inv

# -------------------------
# Lists used by the app
# -------------------------
def list_two_week_invoices(window_start_utc: int, window_end_utc: int):
    """
    Return invoices created in the two-week window (any status),
    with expanded lines and metadata so we can derive bookings.
    """
    params = {
        "created": {"gte": int(window_start_utc) - 3600, "lte": int(window_end_utc) + 3600},
        "limit": 100,
        "expand": ["data.customer", "data.lines.data.price.product"],
    }
    items = []
    for inv in stripe.Invoice.list(**params).auto_paging_iter():
        items.append(inv)
    return items

def list_recent_invoices(limit=None):
    s = _api()
    resp = s.Invoice.list(limit=100)
    out = []
    for inv in resp.auto_paging_iter():
        if isinstance(inv, dict):
            idv = inv.get("id")
            status = inv.get("status")
            total = inv.get("total")
            currency = inv.get("currency")
            customer_email = inv.get("customer_email")
            customer_name = inv.get("customer_name")
            url = inv.get("hosted_invoice_url")
            created = inv.get("created")
        else:
            idv = getattr(inv, "id", None)
            status = getattr(inv, "status", None)
            total = getattr(inv, "total", None)
            currency = getattr(inv, "currency", None)
            customer_email = getattr(inv, "customer_email", None)
            customer_name = getattr(inv, "customer_name", None)
            url = getattr(inv, "hosted_invoice_url", None)
            created = getattr(inv, "created", None)
        out.append({
            "id": idv,
            "status": status,
            "total": total,
            "currency": currency,
            "customer_email": customer_email,
            "customer_name": customer_name,
            "hosted_invoice_url": url,
            "created": created,
        })
        if isinstance(limit, int) and limit > 0 and len(out) >= limit:
            break
    return out

def list_booking_services():
    """
    One entry per ACTIVE, one-time Stripe Price for the Services dropdown.
    Skips recurring prices (those belong on the Subscriptions tab).
    Returns items with 'display' key for LineItemsDialog compatibility.
    """
    out = []
    prices = stripe.Price.list(active=True, expand=["data.product"], limit=100)
    for p in prices.auto_paging_iter():
        prod = p.product
        if getattr(p, "recurring", None):
            continue
        if not getattr(prod, "active", True):
            continue
        if (p.currency or "").lower() != "aud":
            continue
        md = {}
        md.update(getattr(prod, "metadata", {}) or {})
        md.update(getattr(p, "metadata", {}) or {})
        base_label = p.nickname or prod.name or "Service"
        amount_cents = p.unit_amount or 0
        label = f"{base_label} — ${amount_cents/100:.2f}"
        
        # Create display_short for service_name in line items
        display_short = p.nickname or prod.name or "Service"
        
        out.append({
            "label": label,
            "display": label,  # Required by LineItemsDialog
            "display_short": display_short,  # For service_name in line items
            "service_code": md.get("service_code") or (base_label.upper().replace(" ", "_")),
            "price_id": p.id,
            "unit_amount_cents": amount_cents,  # Consistent naming
            "amount_cents": amount_cents,  # Keep for backward compatibility
            "capacity_type": md.get("capacity_type") or "walk",
            "product_id": prod.id,
            "product_name": prod.name or "",
            "price_nickname": p.nickname or "",
            "metadata": md,
        })
    out.sort(key=lambda s: s["label"].lower())
    return out

def list_catalog_for_line_items():
    """
    Normalized catalog for line items dialog with guaranteed 'display' key.
    """
    out = []
    for price in stripe.Price.list(active=True, expand=["data.product"]).auto_paging_iter():
        amount_cents = int(price.unit_amount or 0)
        nickname = getattr(price, "nickname", None)
        prod = getattr(price, "product", None)
        prod_name = getattr(prod, "name", None) if prod else None
        display = nickname or prod_name or price.id
        out.append({
            "price_id": price.id,
            "amount_cents": amount_cents,
            "price_nickname": nickname,
            "product_id": getattr(prod, "id", None) if prod else None,
            "product_name": prod_name,
            "display": display,         # <-- guaranteed now
        })
    return out

def list_products():
    s = _api()
    prods = s.Product.list(active=True, limit=100)
    out = []
    for p in prods.auto_paging_iter():
        if isinstance(p, dict):
            out.append({"id": p.get("id"), "name": p.get("name")})
        else:
            out.append({"id": getattr(p, "id", None), "name": getattr(p, "name", None)})
    return out

# Robust helper: list_active_subscriptions_from_stripe
import logging
from typing import List

def list_active_subscriptions_from_stripe(status: str = "active", limit: int = 100, expand=None) -> List:
    """Return list of Stripe subscription objects (or dict-like) using safe iteration.

    Example: list_active_subscriptions_from_stripe(limit=100, expand=['data.customer', 'data.items.data.price'])
    """
    import stripe
    from log_utils import get_subscription_logger, log_subscription_error
    try:
        from secrets_config import get_stripe_key
    except Exception:
        get_stripe_key = None

    logger = get_subscription_logger() if 'get_subscription_logger' in globals() else logging.getLogger(__name__)

    # Configure API key if helper available
    if get_stripe_key:
        try:
            stripe.api_key = get_stripe_key()
        except Exception:
            pass

    try:
        params = {"limit": limit}
        if expand:
            params["expand"] = expand
        resp = stripe.Subscription.list(**params)
    except Exception as e:
        logger.error(f"Error calling stripe.Subscription.list: {e}")
        try:
            log_subscription_error("Error listing subscriptions", "all", e)
        except Exception:
            pass
        return []

    subs = []
    try:
        api_iter = getattr(resp, "auto_paging_iter", None)
        if callable(api_iter):
            for item in resp.auto_paging_iter():
                subs.append(item)
        elif hasattr(resp, "data"):
            subs = list(resp.data or [])
        else:
            try:
                subs = list(resp)
            except Exception:
                logger.warning("Unexpected Stripe response shape when listing subscriptions")
                subs = []
    except Exception as e:
        logger.error(f"Error iterating stripe subscriptions response: {e}")
        try:
            subs = list(resp.data) if hasattr(resp, "data") else []
        except Exception:
            subs = []

    return subs

def list_subscriptions(limit: int = 100):
    """Return simplified subscription dicts for UI consumption using the robust helper."""
    from log_utils import get_subscription_logger, log_subscription_error
    logger = get_subscription_logger() if 'get_subscription_logger' in globals() else logging.getLogger(__name__)

    subs = list_active_subscriptions_from_stripe(limit=limit, expand=['data.customer', 'data.items.data.price', 'data.latest_invoice'])
    out = []
    for sub in subs:
        subscription_id = 'unknown'
        try:
            # Support both dict-like and Stripe object shapes
            if hasattr(sub, 'get') and callable(getattr(sub, 'get')):
                sub_obj = sub
                subscription_id = sub_obj.get('id', 'unknown')
                status = sub_obj.get('status')
                customer_obj = sub_obj.get('customer', {}) or {}
            else:
                subscription_id = getattr(sub, 'id', 'unknown')
                status = getattr(sub, 'status', None)
                customer_obj = getattr(sub, 'customer', None) or {}

            c_email = customer_obj.get('email') if hasattr(customer_obj, 'get') else getattr(customer_obj, 'email', None)
            c_name = customer_obj.get('name') if hasattr(customer_obj, 'get') else getattr(customer_obj, 'name', None)
            customer_id = customer_obj.get('id') if hasattr(customer_obj, 'get') else getattr(customer_obj, 'id', None)

            # Extract product names safely
            products = []
            items_block = sub_obj.get('items') if isinstance(sub_obj, dict) else getattr(sub, 'items', None)
            data_list = []
            if hasattr(items_block, 'get') and callable(getattr(items_block, 'get')):
                data_list = items_block.get('data', []) or []
            elif hasattr(items_block, 'data'):
                data_list = getattr(items_block, 'data') or []
            else:
                try:
                    data_list = list(items_block or [])
                except Exception:
                    data_list = []

            for it in data_list:
                price_obj = it.get('price') if hasattr(it, 'get') else getattr(it, 'price', None)
                prod = price_obj.get('product') if hasattr(price_obj, 'get') else getattr(price_obj, 'product', None)
                pname = None
                try:
                    if isinstance(prod, str) and prod.startswith('prod_'):
                        s = _api()
                        p = s.Product.retrieve(prod)
                        pname = getattr(p, 'name', None)
                    elif hasattr(prod, 'get') and callable(getattr(prod, 'get')):
                        pname = prod.get('name')
                    elif hasattr(prod, 'name'):
                        pname = getattr(prod, 'name', None)
                except Exception:
                    pname = None
                if pname:
                    products.append(pname)

            latest_inv = sub_obj.get('latest_invoice') if isinstance(sub_obj, dict) else getattr(sub, 'latest_invoice', None)
            latest_url = None
            try:
                if hasattr(latest_inv, 'get') and callable(getattr(latest_inv, 'get')):
                    latest_url = latest_inv.get('hosted_invoice_url')
                elif hasattr(latest_inv, 'hosted_invoice_url'):
                    latest_url = getattr(latest_inv, 'hosted_invoice_url', None)
            except Exception:
                latest_url = None

            subscription_result = {
                'id': subscription_id,
                'status': status,
                'customer_id': customer_id,
                'customer_email': c_email,
                'customer_name': c_name,
                'products': ', '.join(products) if products else '',
                'current_period_end': (sub_obj.get('current_period_end') if isinstance(sub_obj, dict) else getattr(sub, 'current_period_end', None)),
                'latest_invoice_url': latest_url,
            }
            out.append(subscription_result)
            if isinstance(limit, int) and limit > 0 and len(out) >= limit:
                break
        except Exception as e:
            try:
                log_subscription_error('Error processing individual subscription', subscription_id, e)
            except Exception:
                logger.exception(e)
            continue

    return out

def list_all_customers(limit=None):
    s = _api()
    resp = s.Customer.list(limit=100)
    out = []
    for cu in resp.auto_paging_iter():
        if isinstance(cu, dict):
            address = cu.get("address") or {}
            address_line = []
            if address.get("line1"): address_line.append(address.get("line1"))
            if address.get("line2"): address_line.append(address.get("line2"))
            if address.get("city"): address_line.append(address.get("city"))
            if address.get("state"): address_line.append(address.get("state"))
            if address.get("postal_code"): address_line.append(address.get("postal_code"))
            if address.get("country"): address_line.append(address.get("country"))
            full_address = ", ".join(address_line) if address_line else ""
            out.append({
                "id": cu.get("id"),
                "email": cu.get("email"),
                "name": cu.get("name"),
                "phone": cu.get("phone"),
                "address": full_address
            })
        else:
            address = getattr(cu, "address", None) or {}
            address_line = []
            if hasattr(address, 'line1') and address.line1:
                address_line.append(address.line1)
            elif isinstance(address, dict) and address.get("line1"):
                address_line.append(address.get("line1"))
            if hasattr(address, 'line2') and address.line2:
                address_line.append(address.line2)
            elif isinstance(address, dict) and address.get("line2"):
                address_line.append(address.get("line2"))
            if hasattr(address, 'city') and address.city:
                address_line.append(address.city)
            elif isinstance(address, dict) and address.get("city"):
                address_line.append(address.get("city"))
            if hasattr(address, 'state') and address.state:
                address_line.append(address.state)
            elif isinstance(address, dict) and address.get("state"):
                address_line.append(address.get("state"))
            if hasattr(address, 'postal_code') and address.postal_code:
                address_line.append(address.postal_code)
            elif isinstance(address, dict) and address.get("postal_code"):
                address_line.append(address.get("postal_code"))
            if hasattr(address, 'country') and address.country:
                address_line.append(address.country)
            elif isinstance(address, dict) and address.get("country"):
                address_line.append(address.get("country"))
            full_address = ", ".join(address_line) if address_line else ""
            out.append({
                "id": getattr(cu,"id",None),
                "email": getattr(cu,"email",None),
                "name": getattr(cu,"name",None),
                "phone": getattr(cu,"phone",None),
                "address": full_address
            })
        if isinstance(limit,int) and limit>0 and len(out)>=limit:
            break
    return out

def list_outstanding_invoices(limit=500):
    """
    Return Stripe invoices that are OPEN or UNCOLLECTIBLE.
    Includes customer info and hosted_invoice_url for quick open.
    """
    s = _api()
    out = []

    def _collect(status):
        resp = s.Invoice.list(limit=100, status=status, expand=['data.customer'])
        for inv in resp.auto_paging_iter():
            if isinstance(inv, dict):
                d = inv
                cid = d.get("customer")
                if isinstance(cid, dict):
                    cname = cid.get("name"); cemail = cid.get("email"); customer_id = cid.get("id")
                else:
                    cname = d.get("customer_name"); cemail = d.get("customer_email"); customer_id = cid
                out.append({
                    "id": d.get("id"),
                    "created": d.get("created"),
                    "status": d.get("status"),
                    "total": d.get("total"),
                    "currency": d.get("currency"),
                    "customer_id": customer_id,
                    "customer_name": cname,
                    "customer_email": cemail,
                    "hosted_invoice_url": d.get("hosted_invoice_url"),
                })
            else:
                cid = getattr(inv, "customer", None)
                cname = getattr(inv, "customer_name", None)
                cemail = getattr(inv, "customer_email", None)
                if isinstance(cid, dict):
                    customer_id = cid.get("id")
                    cname = cid.get("name") or cname
                    cemail = cid.get("email") or cemail
                else:
                    customer_id = cid
                out.append({
                    "id": getattr(inv, "id", None),
                    "created": getattr(inv, "created", None),
                    "status": getattr(inv, "status", None),
                    "total": getattr(inv, "total", None),
                    "currency": getattr(inv, "currency", None),
                    "customer_id": customer_id,
                    "customer_name": cname,
                    "customer_email": cemail,
                    "hosted_invoice_url": getattr(inv, "hosted_invoice_url", None),
                })

    _collect("open")
    _collect("uncollectible")

    # de-dupe by id
    uniq = {}
    for r in out:
        uniq[r["id"]] = r
    return list(uniq.values())

def get_subscription_details(subscription_id):
    """Get subscription details including customer information"""
    try:
        sub = stripe.Subscription.retrieve(subscription_id, expand=['customer'])
        customer = sub.customer
        return {
            "id": sub.id,
            "status": sub.status,
            "customer_id": customer.id if customer else None,
            "customer_email": customer.email if customer else None,
            "customer_name": customer.name if customer else None,
        }
    except Exception:
        return {}

def list_active_subscriptions(limit=200):
    """
    Returns active, trialing, or past_due subscriptions with simplified, reliable filtering.
    
    Simplified approach to prevent valid subscriptions from being incorrectly filtered out.
    All fields needed for booking creation are reliably extracted.
    Straightforward error logging with no silent failures.
    """
    s = _api()
    out = []
    
    try:
        subs = list_active_subscriptions_from_stripe(
            limit=limit, 
            expand=['data.customer', 'data.items.data.price', 'data.latest_invoice']
        )
        
        for sub in subs:
            # Support both dict-like and Stripe object shapes
            if hasattr(sub, 'get') and callable(getattr(sub, 'get')):
                sub_status = sub.get('status')
                sub_id = sub.get('id')
                sub_customer = sub.get('customer')
                sub_items = sub.get('items')
                sub_latest_invoice = sub.get('latest_invoice')
                sub_metadata = sub.get('metadata', {})
            else:
                sub_status = getattr(sub, 'status', None)
                sub_id = getattr(sub, 'id', None)
                sub_customer = getattr(sub, 'customer', None)
                sub_items = getattr(sub, 'items', None)
                sub_latest_invoice = getattr(sub, 'latest_invoice', None)
                sub_metadata = getattr(sub, 'metadata', {})
                
            if sub_status in ("active", "trialing", "past_due"):
                # Extract basic subscription data
                customer_id = customer_email = customer_name = None
                if sub_customer:
                    if hasattr(sub_customer, 'get') and callable(getattr(sub_customer, 'get')):
                        customer_id = sub_customer.get('id')
                        customer_email = sub_customer.get('email')
                        customer_name = sub_customer.get('name')
                    else:
                        customer_id = getattr(sub_customer, 'id', None)
                        customer_email = getattr(sub_customer, 'email', None)
                        customer_name = getattr(sub_customer, 'name', None)
                        
                subscription_result = {
                    "id": sub_id,
                    "status": sub_status,
                    "customer_id": customer_id,
                    "customer_email": customer_email,
                    "customer_name": customer_name,
                }
                
                # Add customer display name for UI compatibility
                if subscription_result["customer_name"] and subscription_result["customer_email"]:
                    subscription_result["customer_display_name"] = f"{subscription_result['customer_name']} ({subscription_result['customer_email']})"
                elif subscription_result["customer_name"]:
                    subscription_result["customer_display_name"] = subscription_result["customer_name"]
                elif subscription_result["customer_email"]:
                    subscription_result["customer_display_name"] = subscription_result["customer_email"]
                elif subscription_result["customer_id"]:
                    subscription_result["customer_display_name"] = f"Customer {subscription_result['customer_id']}"
                else:
                    subscription_result["customer_display_name"] = "Unknown Customer"
                
                # Calculate weekly quantity for UI
                weekly_qty = 0
                item_rows = []
                items_data = []
                if sub_items:
                    if hasattr(sub_items, 'get') and callable(getattr(sub_items, 'get')):
                        items_data = sub_items.get('data', []) or []
                    elif hasattr(sub_items, 'data'):
                        items_data = getattr(sub_items, 'data', []) or []
                    
                if items_data:
                    for item in items_data:
                        if hasattr(item, 'get') and callable(getattr(item, 'get')):
                            qty = int(item.get('quantity', 0) or 0)
                            price = item.get('price')
                        else:
                            qty = int(getattr(item, 'quantity', 0) or 0)
                            price = getattr(item, 'price', None)
                        
                        # Calculate weekly quantity using existing helper
                        weekly_qty += calculate_weekly_quantity(price, qty)
                        
                        # Extract item details for UI
                        product_name = None
                        if price:
                            price_product = None
                            if hasattr(price, 'get') and callable(getattr(price, 'get')):
                                price_product = price.get('product')
                            else:
                                price_product = getattr(price, 'product', None)
                                
                            if price_product:
                                if isinstance(price_product, str):
                                    try:
                                        product_name = s.Product.retrieve(price_product).name
                                    except Exception:
                                        product_name = price_product
                                else:
                                    product_name = getattr(price_product, 'name', None)
                        
                        price_id = price.get('id') if hasattr(price, 'get') else getattr(price, 'id', None)
                        price_nickname = price.get('nickname') if hasattr(price, 'get') else getattr(price, 'nickname', None)
                        price_unit_amount = price.get('unit_amount') if hasattr(price, 'get') else getattr(price, 'unit_amount', None)
                        
                        price_recurring = price.get('recurring') if hasattr(price, 'get') else getattr(price, 'recurring', None)
                        price_interval = None
                        if price_recurring:
                            if hasattr(price_recurring, 'get') and callable(getattr(price_recurring, 'get')):
                                price_interval = price_recurring.get('interval')
                            else:
                                price_interval = getattr(price_recurring, 'interval', None)
                        
                        item_rows.append({
                            "price_id": price_id,
                            "product_name": product_name,
                            "nickname": price_nickname,
                            "quantity": qty,
                            "unit_amount": price_unit_amount,
                            "interval": price_interval,
                        })
                
                subscription_result["weekly_quantity"] = weekly_qty
                subscription_result["items"] = item_rows
                
                # Extract latest invoice URL
                latest_url = None
                if sub_latest_invoice:
                    if hasattr(sub_latest_invoice, 'get') and callable(getattr(sub_latest_invoice, 'get')):
                        latest_url = sub_latest_invoice.get('hosted_invoice_url')
                    else:
                        latest_url = getattr(sub_latest_invoice, 'hosted_invoice_url', None)
                subscription_result["latest_invoice_url"] = latest_url
                
                # Include metadata and customer data for downstream processing
                subscription_result["metadata"] = sub_metadata or {}
                subscription_result["customer"] = sub_customer if sub_customer else {}
                
                out.append(subscription_result)
        
        print(f"Debug: Found {len(out)} active subscriptions")
        return out
        
    except Exception as e:
        print(f"Error listing active subscriptions: {e}")
        return []

def cancel_subscription(subscription_id: str) -> bool:
    """
    Cancel a subscription in Stripe.
    
    Args:
        subscription_id: Stripe subscription ID to cancel
        
    Returns:
        True if successful, False otherwise
    """
    try:
        s = _api()
        subscription = s.Subscription.modify(
            subscription_id,
            cancel_at_period_end=False  # Cancel immediately
        )
        # Actually cancel the subscription
        subscription = s.Subscription.cancel(subscription_id)
        return subscription.status == 'canceled'
    except Exception as e:
        print(f"Error canceling subscription {subscription_id}: {e}")
        return False
