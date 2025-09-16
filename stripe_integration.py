# stripe_integration.py  — replace the whole file with this
# (⚠️ Sensitive: contains your live Stripe key. Do NOT share or commit publicly.)

import os, webbrowser
import stripe
from datetime import datetime, timezone, timedelta

# 🔒 Hard-wired live key so you never need env vars in the app
stripe.api_key = "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"

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

def list_subscriptions(limit=100):
    """
    List subscriptions with robust customer display logic.
    
    This function ensures every subscription object ALWAYS stores the Stripe customer ID
    and implements proper fallback when displaying customer information as per requirements:
    1. If customer_id exists, always fetch from Stripe API when needed
    2. Never display 'Unknown Customer' if customer_id exists and API is accessible  
    3. Use fallback: Customer {id} (Stripe API error) for API failures
    4. Robust error logging for all failures
    """
    from customer_display_helpers import get_robust_customer_display_info
    from log_utils import get_subscription_logger, log_subscription_error
    
    s = _api()
    logger = get_subscription_logger()
    
    try:
        subs = s.Subscription.list(limit=limit, expand=['data.customer', 'data.latest_invoice'])
        out = []
        
        for sub in subs.auto_paging_iter():
            subscription_id = "unknown"  # Initialize subscription_id for error handling
            try:
                # Handle both dict and Stripe object formats safely
                # First, try to get the basic id for error logging
                if hasattr(sub, 'get') and callable(sub.get):
                    # It's a dict-like object
                    sub_dict = sub
                    subscription_id = sub_dict.get("id", "unknown")
                elif hasattr(sub, 'id'):
                    # It has an id attribute
                    subscription_id = getattr(sub, 'id', 'unknown')
                    # Convert Stripe object to dict for easier access
                    if hasattr(sub, '__dict__') and not hasattr(sub, 'get'):
                        # Real Stripe object - be careful with mocks that don't have __dict__ properly
                        try:
                            sub_dict = {k: getattr(sub, k, None) for k in dir(sub) if not k.startswith('_') and not callable(getattr(sub, k, None))}
                        except AttributeError:
                            # Mock object causing issues, use fallback
                            sub_dict = {}
                            for attr in ['id', 'status', 'customer', 'items', 'current_period_end', 'latest_invoice']:
                                try:
                                    sub_dict[attr] = getattr(sub, attr, None)
                                except AttributeError:
                                    sub_dict[attr] = None
                    else:
                        # Mock object or dict-like, handle carefully  
                        sub_dict = {}
                        for attr in ['id', 'status', 'customer', 'items', 'current_period_end', 'latest_invoice']:
                            try:
                                sub_dict[attr] = getattr(sub, attr, None)
                            except AttributeError:
                                sub_dict[attr] = None
                else:
                    # Fallback: create basic dict with essential fields
                    sub_dict = {}
                    for attr in ['id', 'status', 'customer', 'items', 'current_period_end', 'latest_invoice']:
                        try:
                            sub_dict[attr] = getattr(sub, attr, None)
                        except AttributeError:
                            sub_dict[attr] = None
                    subscription_id = sub_dict.get("id", "unknown")
                
                subscription_id = sub_dict.get("id") or getattr(sub, "id", "unknown")
                
                # Extract customer information with robust fallback
                customer_data = sub_dict.get("customer") or getattr(sub, "customer", None)
                
                # Ensure customer_id is always captured and stored
                customer_id = None
                try:
                    if hasattr(customer_data, 'get') and callable(customer_data.get):
                        customer_id = customer_data.get("id")
                    elif hasattr(customer_data, 'id'):
                        customer_id = getattr(customer_data, "id", None)
                    elif customer_data:
                        # Try to access as string (customer ID directly)
                        customer_id = str(customer_data) if customer_data else None
                except Exception:
                    customer_id = None
                    
                if not customer_id:
                    log_subscription_error("Missing customer_id in subscription", subscription_id)
                
                # Get robust customer display info using dedicated helper
                customer_display_name = get_robust_customer_display_info({
                    'id': subscription_id,
                    'customer': customer_data
                })
                
                # Extract customer email for consistency
                c_email = ""
                try:
                    if hasattr(customer_data, 'get') and callable(customer_data.get):
                        c_email = customer_data.get("email", "")
                    elif hasattr(customer_data, 'email'):
                        c_email = getattr(customer_data, "email", "")
                except Exception:
                    c_email = ""
                
                # Extract products
                items_block = sub_dict.get("items") or getattr(sub, "items", None)
                data_list = []
                try:
                    if hasattr(items_block, 'get') and callable(items_block.get):
                        data_list = items_block.get("data", []) or []
                    elif hasattr(items_block, 'data'):
                        data_list = getattr(items_block, "data", []) or []
                except Exception:
                    data_list = []
                
                products = []
                for it in data_list:
                    try:
                        # Handle both dict and object formats safely
                        if hasattr(it, 'get') and callable(it.get):
                            it_dict = it
                        elif hasattr(it, '__dict__'):
                            it_dict = {k: getattr(it, k, None) for k in dir(it) if not k.startswith('_')}
                        else:
                            it_dict = {'price': getattr(it, 'price', None)}
                            
                        price = it_dict.get("price") or getattr(it, "price", None)
                        
                        # Handle price object safely
                        prod = None
                        if hasattr(price, 'get') and callable(price.get):
                            prod = price.get("product")
                        elif hasattr(price, 'product'):
                            prod = getattr(price, "product", None)
                            
                        pname = None
                        try:
                            # Handle string product ID
                            if hasattr(prod, 'startswith') and callable(prod.startswith) and prod.startswith('prod_'):
                                pname = s.Product.retrieve(prod).name
                            # Handle dict-like product object
                            elif hasattr(prod, 'get') and callable(prod.get):
                                pname = prod.get("name")
                            # Handle object with name attribute
                            elif hasattr(prod, 'name'):
                                pname = getattr(prod, "name", None)
                        except Exception as e:
                            logger.warning(f"Failed to get product name: {e}")
                            pname = None
                            
                        if pname:
                            products.append(pname)
                    except Exception as e:
                        logger.warning(f"Error processing subscription item: {e}")
                
                # Extract latest invoice URL
                latest_inv = sub_dict.get("latest_invoice") or getattr(sub, "latest_invoice", None)
                latest_url = None
                try:
                    if hasattr(latest_inv, 'get') and callable(latest_inv.get):
                        latest_url = latest_inv.get("hosted_invoice_url")
                    elif hasattr(latest_inv, 'hosted_invoice_url'):
                        latest_url = getattr(latest_inv, "hosted_invoice_url", None)
                except Exception:
                    latest_url = None
                
                # Build subscription result with customer_id always included
                subscription_result = {
                    "id": subscription_id,
                    "customer_id": customer_id,  # ALWAYS store customer_id as per requirements
                    "status": sub_dict.get("status") or getattr(sub, "status", None),
                    "customer_email": c_email,
                    "customer_name": customer_display_name,
                    "products": ", ".join(products) if products else "",
                    "current_period_end": sub_dict.get("current_period_end") or getattr(sub, "current_period_end", None),
                    "latest_invoice_url": latest_url,
                }
                
                out.append(subscription_result)
                
                if isinstance(limit, int) and limit > 0 and len(out) >= limit:
                    break
                    
            except Exception as e:
                log_subscription_error("Error processing individual subscription", subscription_id, e)
                continue
                
        return out
        
    except Exception as e:
        log_subscription_error("Error listing subscriptions", "all", e)
        return []

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
    Returns active-like subscriptions with robust customer info and weekly_quantity.
    
    This function ensures customer information is always available by fetching
    from Stripe API when needed, preventing "Unknown Customer" issues.
    
    Every subscription ALWAYS includes customer_id as per requirements.
    """
    from customer_display_helpers import ensure_customer_data_in_subscription
    from log_utils import log_subscription_error, get_subscription_logger
    
    s = _api()
    logger = get_subscription_logger()
    out = []
    
    try:
        # Expand items + price + customer to get complete data
        subs = s.Subscription.list(limit=limit, expand=['data.customer', 'data.items.data.price', 'data.latest_invoice'])
        
        for sub in subs.auto_paging_iter():
            try:
                # Handle both dict and Stripe object formats safely
                if hasattr(sub, '__dict__'):
                    # Stripe object - convert to dict for easier access
                    d = {k: getattr(sub, k, None) for k in dir(sub) if not k.startswith('_')}
                elif isinstance(sub, dict):
                    d = sub
                else:
                    # Fallback: create basic dict with essential fields
                    d = {
                        'id': getattr(sub, 'id', None),
                        'status': getattr(sub, 'status', None),
                        'customer': getattr(sub, 'customer', None),
                        'items': getattr(sub, 'items', None),
                        'latest_invoice': getattr(sub, 'latest_invoice', None)
                    }
                
                status = d.get("status")
                if status not in ("active", "trialing", "past_due"):
                    continue
                
                subscription_id = d.get("id") or getattr(sub, "id", "unknown")
                
                # Ensure customer data is complete - REQUIREMENT: Always store customer_id
                d = ensure_customer_data_in_subscription(d)

                # Enhanced customer handling with Stripe API fallback
                cust = d.get("customer") or getattr(sub, "customer", None)
                customer_id = None
                c_name = None
                c_email = None
                
                if isinstance(cust, dict):
                    c_email = cust.get("email")
                    c_name = cust.get("name")
                    customer_id = cust.get("id")
                elif isinstance(cust, str):
                    # Customer is just an ID, need to fetch details
                    customer_id = cust
                elif cust:
                    c_email = getattr(cust, "email", None)
                    c_name = getattr(cust, "name", None)
                    customer_id = getattr(cust, "id", None)

                if not customer_id:
                    log_subscription_error("Missing customer_id in active subscription", subscription_id)
                    continue  # Skip subscriptions without customer_id
                
                # Always try to fetch customer data from Stripe if we don't have name/email
                customer_display_name = c_name
                if (not customer_display_name or not c_email) and customer_id:
                    try:
                        logger.debug(f"Fetching customer details for {customer_id}")
                        customer_obj = s.Customer.retrieve(customer_id)
                        fetched_name = getattr(customer_obj, "name", None)
                        fetched_email = getattr(customer_obj, "email", None)
                        
                        # Use fetched data to fill in missing info
                        customer_display_name = fetched_name or customer_display_name
                        c_email = fetched_email or c_email
                        c_name = fetched_name or c_name
                        
                        # Update customer object in subscription data for downstream use
                        d["customer"] = {
                            "id": customer_id,
                            "name": fetched_name or "",
                            "email": fetched_email or "",
                        }
                        
                    except Exception as e:
                        logger.warning(f"Failed to fetch customer {customer_id}: {e}")
                
                # Final customer display name with robust fallback
                if customer_display_name and c_email:
                    customer_display_name = f"{customer_display_name} ({c_email})"
                elif customer_display_name:
                    pass  # Use name as-is
                elif c_email:
                    customer_display_name = c_email
                elif customer_id:
                    # As per requirements: Customer {id} instead of 'Unknown Customer' when ID exists
                    customer_display_name = f"Customer {customer_id}"
                else:
                    customer_display_name = "Unknown Customer"

                # items
                items_block = d.get("items") or getattr(sub, "items", None)
                items_list = items_block.get("data", []) if isinstance(items_block, dict) else getattr(items_block, "data", []) or []

                weekly_qty = 0
                item_rows = []
                for it in items_list:
                    try:
                        if isinstance(it, dict):
                            it_d = it
                        elif hasattr(it, '__dict__'):
                            it_d = {k: getattr(it, k, None) for k in dir(it) if not k.startswith('_')}
                        else:
                            it_d = {'quantity': getattr(it, 'quantity', 0), 'price': getattr(it, 'price', None)}
                            
                        qty = int(it_d.get("quantity") or 0)
                        price = it_d.get("price") or getattr(it, "price", None)

                        # Use the helper function to calculate weekly quantity
                        weekly_qty += calculate_weekly_quantity(price, qty)

                        # Get interval for item_rows
                        if isinstance(price, dict):
                            rec = price.get("recurring")
                        elif price:
                            rec = getattr(price, "recurring", None)
                        else:
                            rec = None
                            
                        interval = rec.get("interval") if isinstance(rec, dict) else getattr(rec, "interval", None)

                        # product name / info for UI
                        if isinstance(price, dict):
                            product = price.get("product")
                        elif price:
                            product = getattr(price, "product", None)
                        else:
                            product = None
                            
                        if isinstance(product, dict):
                            pname = product.get("name")
                        elif isinstance(product, str):
                            try:
                                pname = s.Product.retrieve(product).name
                            except Exception:
                                pname = None
                        elif product:
                            pname = getattr(product, "name", None)
                        else:
                            pname = None

                        if isinstance(price, dict):
                            nickname = price.get("nickname")
                            unit_amount = price.get("unit_amount")
                            price_id = price.get("id")
                        elif price:
                            nickname = getattr(price, "nickname", None)
                            unit_amount = getattr(price, "unit_amount", None)
                            price_id = getattr(price, "id", None)
                        else:
                            nickname = None
                            unit_amount = None
                            price_id = None

                        item_rows.append({
                            "price_id": price_id,
                            "product_name": pname,
                            "nickname": nickname,
                            "quantity": qty,
                            "unit_amount": unit_amount,
                            "interval": interval,
                        })
                    except Exception as e:
                        logger.warning(f"Error processing subscription item: {e}")
                        continue

                latest_inv = d.get("latest_invoice") or getattr(sub, "latest_invoice", None)
                latest_url = latest_inv.get("hosted_invoice_url") if isinstance(latest_inv, dict) else getattr(latest_inv, "hosted_invoice_url", None)

                # Build subscription result - ALWAYS include customer_id as per requirements
                subscription_result = {
                    "id": subscription_id,
                    "status": status,
                    "customer_id": customer_id,  # REQUIRED: Always include customer_id
                    "customer_email": c_email,
                    "customer_name": c_name,
                    "customer_display_name": customer_display_name,
                    "weekly_quantity": weekly_qty,
                    "items": item_rows,
                    "latest_invoice_url": latest_url,
                    "metadata": d.get("metadata", {}),  # Include metadata for schedule extraction
                    "customer": d.get("customer"),  # Include full customer data for downstream use
                }
                
                out.append(subscription_result)
                
            except Exception as e:
                subscription_id = getattr(sub, "id", "unknown")
                log_subscription_error("Error processing individual active subscription", subscription_id, e)
                continue
                
        return out
        
    except Exception as e:
        log_subscription_error("Error listing active subscriptions", "all", e)
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
