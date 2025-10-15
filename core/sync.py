from __future__ import annotations
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict

import stripe
from django.db import transaction
from django.apps import apps
from django.utils.timezone import make_aware

log = logging.getLogger(__name__)

# ---------- Helpers ----------

def _get_model(app_label: str, model_name: str):
    """Return model class or None if it doesn't exist."""
    try:
        return apps.get_model(app_label, model_name)
    except Exception:
        return None

def _set_if_has(obj, field: str, value: Any):
    """Set obj.field only if it exists on the model."""
    if hasattr(obj, field):
        setattr(obj, field, value)

def _dt(ts: Optional[int]) -> Optional[datetime]:
    if not ts:
        return None
    return make_aware(datetime.fromtimestamp(ts, tz=timezone.utc))

def _ensure_stripe():
    # Try multiple environment variable names
    api_key = os.getenv("STRIPE_API_KEY", "").strip()
    if not api_key:
        api_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not api_key:
        raise RuntimeError("STRIPE_API_KEY or STRIPE_SECRET_KEY missing")
    stripe.api_key = api_key
    # make requests modestly sized
    stripe.default_http_client = stripe.http_client.new_default_http_client(timeout=30)

def _find_or_create_client(stripe_cust: Dict[str, Any], Client):
    # We try multiple unique keys in a stable order
    email = (stripe_cust.get("email") or "").strip().lower() or None
    sid = stripe_cust.get("id")
    name = stripe_cust.get("name") or ""

    qs = None
    if hasattr(Client, "stripe_customer_id") and sid:
        qs = Client.objects.filter(stripe_customer_id=sid)
    elif hasattr(Client, "email") and email:
        qs = Client.objects.filter(email=email)

    obj = qs.first() if qs is not None else None
    created = False
    if not obj:
        created = True
        obj = Client()
        _set_if_has(obj, "stripe_customer_id", sid)

    # map common fields if they exist
    _set_if_has(obj, "name", name or (email or sid))
    _set_if_has(obj, "email", email)
    # Phone/address live in customer['address'] or customer['phone']
    addr = stripe_cust.get("address") or {}
    phone = stripe_cust.get("phone") or None
    full_addr = ", ".join([str(addr.get(k)) for k in ("line1","line2","city","state","postal_code") if addr.get(k)])
    _set_if_has(obj, "phone", phone)
    _set_if_has(obj, "address", full_addr if full_addr else None)
    obj.save()
    return obj, created

def _find_or_create_booking(source_key: str, client, Booking, start_at: datetime, end_at: datetime):
    """
    source_key is a stable unique key such as 'sub_<sid>_<period_start>' or 'inv_<id>'.
    Booking model is prob. unique on an external key; we store it if the field exists.
    """
    bk = None
    if hasattr(Booking, "external_key"):
        bk = Booking.objects.filter(external_key=source_key).first()
    if not bk:
        bk = Booking()
        _set_if_has(bk, "external_key", source_key)
    # required associations/timestamps
    if hasattr(bk, "client") and client:
        setattr(bk, "client", client)
    _set_if_has(bk, "start_dt", start_at)
    _set_if_has(bk, "end_dt", end_at or start_at)
    # sensible defaults for status/service/price if present
    _set_if_has(bk, "status", getattr(Booking, "Status", None).CONFIRMED if hasattr(getattr(Booking, "Status", None), "CONFIRMED") else "confirmed")
    _set_if_has(bk, "service_code", getattr(bk, "service_code", None) or "stripe")
    _set_if_has(bk, "service_name", getattr(bk, "service_name", None) or "Stripe")
    _set_if_has(bk, "service_label", getattr(bk, "service_label", None) or "Stripe")
    _set_if_has(bk, "price_cents", getattr(bk, "price_cents", None) or 0)
    _set_if_has(bk, "location", getattr(bk, "location", None) or "")
    bk.save()
    return bk

# ---------- Public sync API used by management commands & scheduler ----------

@transaction.atomic
def sync_customers() -> dict:
    """
    Pull Stripe customers and upsert into your Client model.
    Fields are applied only if they exist on your model.
    """
    _ensure_stripe()
    Client = _get_model("core", "Client") or _get_model("newfarm", "Client")
    if not Client:
        log.warning("No Client model found (core.Client). Skipping customers sync.")
        return {"processed": 0, "created": 0, "updated": 0}

    created = updated = processed = 0
    params = {"limit": 100}
    for page in stripe.Customer.list(**params).auto_paging_iter():
        processed += 1
        obj, was_created = _find_or_create_client(page, Client)
        if was_created:
            created += 1
        else:
            updated += 1
    log.info("Customer sync complete: processed=%s created=%s updated=%s", processed, created, updated)
    return {"processed": processed, "created": created, "updated": updated}


@transaction.atomic
def build_bookings_from_subscriptions(window_days: int = 60) -> dict:
    """
    Create/refresh Bookings from active subscriptions' current period.
    We generate one booking representing the current_period_start..end.
    """
    _ensure_stripe()
    Client = _get_model("core", "Client") or _get_model("newfarm", "Client")
    Booking = _get_model("core", "Booking") or _get_model("newfarm", "Booking")
    if not Client or not Booking:
        log.warning("Missing Client or Booking model; skipping subscription->booking.")
        return {"processed": 0, "created": 0, "updated": 0}

    created = updated = processed = 0
    now = datetime.now(tz=timezone.utc)
    since = int((now - timedelta(days=window_days)).timestamp())

    subs = stripe.Subscription.list(status="active", created={"gte": since}, limit=100)
    for sub in subs.auto_paging_iter():
        processed += 1
        cust_id = sub.get("customer")
        period = (sub.get("current_period_start"), sub.get("current_period_end"))
        if not (cust_id and period[0] and period[1]):
            continue
        start_at = _dt(period[0])
        end_at = _dt(period[1])

        # Find client
        qs = None
        if Client and hasattr(Client, "stripe_customer_id"):
            qs = Client.objects.filter(stripe_customer_id=cust_id)
        client = qs.first() if qs is not None else None
        if not client:
            # try creating a basic client from Stripe if missing
            try:
                cust = stripe.Customer.retrieve(cust_id)
            except Exception:
                cust = {"id": cust_id}
            client, _ = _find_or_create_client(cust, Client)

        # Create/update booking
        key = f"sub_{sub['id']}_{period[0]}"
        bk = _find_or_create_booking(key, client, Booking, start_at, end_at)
        if bk._state.adding:  # unlikely here; kept for clarity
            created += 1
        else:
            updated += 1
    log.info("Subscription->booking complete: processed=%s created=%s updated=%s", processed, created, updated)
    return {"processed": processed, "created": created, "updated": updated}


@transaction.atomic
def build_bookings_from_invoices(window_days: int = 90) -> dict:
    """
    Create/refresh Bookings for PAID invoices (as single events on invoice date).
    """
    _ensure_stripe()
    Client = _get_model("core", "Client") or _get_model("newfarm", "Client")
    Booking = _get_model("core", "Booking") or _get_model("newfarm", "Booking")
    if not Client or not Booking:
        log.warning("Missing Client or Booking model; skipping invoice->booking.")
        return {"processed": 0, "created": 0, "updated": 0}

    created = updated = processed = 0
    now = datetime.now(tz=timezone.utc)
    since = int((now - timedelta(days=window_days)).timestamp())

    invs = stripe.Invoice.list(status="paid", created={"gte": since}, limit=100)
    for inv in invs.auto_paging_iter():
        processed += 1
        cust_id = inv.get("customer")
        created_ts = inv.get("created")
        if not (cust_id and created_ts):
            continue
        start_at = _dt(created_ts)
        end_at = start_at  # invoice → one moment booking

        # Find client
        qs = None
        if hasattr(Client, "stripe_customer_id"):
            qs = Client.objects.filter(stripe_customer_id=cust_id)
        client = qs.first() if qs is not None else None
        if not client:
            try:
                cust = stripe.Customer.retrieve(cust_id)
            except Exception:
                cust = {"id": cust_id}
            client, _ = _find_or_create_client(cust, Client)

        key = f"inv_{inv['id']}"
        bk = _find_or_create_booking(key, client, Booking, start_at, end_at)
        if bk._state.adding:
            created += 1
        else:
            updated += 1
    log.info("Invoice->booking complete: processed=%s created=%s updated=%s", processed, created, updated)
    return {"processed": processed, "created": created, "updated": updated}


# Convenience for manual runs/tests
def sync_all() -> dict:
    out = {"customers": {}, "subs": {}, "invoices": {}}
    try:
        out["customers"] = sync_customers()
    except Exception as e:
        log.exception("sync_customers failed: %s", e)
    try:
        out["subs"] = build_bookings_from_subscriptions()
    except Exception as e:
        log.exception("build_bookings_from_subscriptions failed: %s", e)
    try:
        out["invoices"] = build_bookings_from_invoices()
    except Exception as e:
        log.exception("build_bookings_from_invoices failed: %s", e)
    log.info("sync_all summary: %s", out)
    return out
