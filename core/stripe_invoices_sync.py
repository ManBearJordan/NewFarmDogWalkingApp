from __future__ import annotations
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional

import stripe
from django.utils.timezone import make_naive, is_aware
from django.db import transaction

from .models import Booking, Client, Service, StripePriceMap
from .invoice_validation import validate_invoice_against_bookings

log = logging.getLogger(__name__)
BRISBANE = ZoneInfo("Australia/Brisbane")


def _parse_iso_local(dt_str: Optional[str]):
    if not dt_str:
        return None
    s = dt_str.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None
    if is_aware(dt):
        dt = dt.astimezone(BRISBANE)
    return make_naive(dt, BRISBANE)


def _stripe_ts_to_local(ts: Optional[int]):
    if not ts:
        return None
    return make_naive(datetime.fromtimestamp(ts, tz=BRISBANE), BRISBANE)


def _safe_get(obj: Any, path: str, default=None):
    """
    Safe dot-path getter for Stripe objs/dicts, e.g. _safe_get(inv, "status_transitions.paid_at")
    """
    parts = path.split(".")
    cur = obj
    for p in parts:
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(p, None)
        else:
            cur = getattr(cur, p, None)
    return cur if cur is not None else default


def _service_from_line(li, md: Dict[str, Any]) -> Optional[Service]:
    """
    Resolve Service for a line using price→service mapping first, otherwise metadata.service_code.
    """
    # 1) Try mapped price
    price_id = _safe_get(li, "price.id")
    if price_id:
        spm = StripePriceMap.objects.filter(price_id=price_id, active=True).select_related("service").first()
        if spm and spm.service and spm.service.is_active:
            return spm.service
    # 2) Fallback to metadata.service_code
    svc_code = (md.get("service_code") or "").strip() if isinstance(md, dict) else None
    if svc_code:
        svc = Service.objects.filter(code=svc_code, is_active=True).first()
        if svc:
            return svc
    return None


def _link_by_metadata(booking_id_val) -> Optional[Booking]:
    try:
        bid = int(str(booking_id_val))
    except Exception:
        return None
    return Booking.objects.filter(id=bid).select_related("service", "client").first()


def _link_by_client_and_time(customer_id: Optional[str], service_code: Optional[str], booking_start: Optional[str]) -> Optional[Booking]:
    """
    Fallback heuristic when booking_id is missing:
      - Map Stripe customer → Client by client.stripe_customer_id
      - Match Booking by (client, service_code, start_time == parsed booking_start)
    """
    if not (customer_id and booking_start):
        return None
    client = Client.objects.filter(stripe_customer_id=customer_id).first()
    if not client:
        return None
    start_dt = _parse_iso_local(booking_start)
    if not start_dt:
        return None
    qs = Booking.objects.filter(client=client, start_dt=start_dt)
    if service_code:
        qs = qs.filter(service__code=service_code)
    return qs.select_related("service", "client").first()


@transaction.atomic
def _update_booking_from_invoice(booking: Booking, invoice, line_item_md: Dict[str, Any]) -> bool:
    """
    Update core invoice fields on Booking.
    Returns True if any field changed.
    """
    changed = False
    inv_id = getattr(invoice, "id", None) or invoice.get("id")
    inv_status = getattr(invoice, "status", None) or invoice.get("status")
    inv_pdf = getattr(invoice, "invoice_pdf", None) or invoice.get("invoice_pdf") or getattr(invoice, "hosted_invoice_url", None) or invoice.get("hosted_invoice_url")
    paid_ts = _safe_get(invoice, "status_transitions.paid_at")
    paid_at = _stripe_ts_to_local(paid_ts) if paid_ts else None

    if booking.stripe_invoice_id != inv_id:
        booking.stripe_invoice_id = inv_id
        changed = True
    if booking.stripe_invoice_status != inv_status:
        booking.stripe_invoice_status = inv_status
        changed = True
    if inv_pdf and booking.invoice_pdf_url != inv_pdf:
        booking.invoice_pdf_url = inv_pdf
        changed = True
    # only set paid_at when invoice is paid (avoid wiping existing)
    # Compare timestamps at second precision to avoid microsecond differences
    if inv_status == "paid" and paid_at:
        existing_ts = int(booking.paid_at.timestamp()) if booking.paid_at else None
        new_ts = int(paid_at.timestamp())
        if existing_ts != new_ts:
            booking.paid_at = paid_at
            changed = True
    if changed:
        booking.save(update_fields=["stripe_invoice_id", "stripe_invoice_status", "invoice_pdf_url", "paid_at"])
    return changed


def _iterate_invoices_since(days: int):
    """
    Generator over recent invoices using Stripe pagination. Expands lines.data.
    """
    since = datetime.now(tz=BRISBANE) - timedelta(days=days)
    starting_after = None
    while True:
        params = {
            "limit": 100,
            "created": {"gte": int(since.timestamp())},
            # include price so we can map to Service
            "expand": ["data.lines.data", "data.lines.data.price"],
        }
        if starting_after:
            params["starting_after"] = starting_after
        page = stripe.Invoice.list(**params)
        data = getattr(page, "data", []) or []
        for inv in data:
            yield inv
        if not getattr(page, "has_more", False):
            break
        starting_after = data[-1].id if data else None


def sync_invoices(days: int = 90) -> Dict[str, int]:
    """
    Pull recent invoices, link them to bookings, update fields, and run metadata validation.
    """
    counts = {
        "processed_invoices": 0,
        "line_items": 0,
        "linked": 0,
        "updated": 0,
        "flagged": 0,
        "unlinked": 0,
        "errors": 0,
    }
    for inv in _iterate_invoices_since(days):
        counts["processed_invoices"] += 1
        try:
            customer_id = getattr(inv, "customer", None)
            lines = getattr(inv, "lines", None)
            line_items = getattr(lines, "data", []) if lines else []
            for li in (line_items or []):
                counts["line_items"] += 1
                md = getattr(li, "metadata", None) or {}
                # resolve service for better matching
                svc = _service_from_line(li, md)
                svc_code = getattr(svc, "code", None)
                booking = None
                # 1) Prefer explicit booking_id
                if "booking_id" in md:
                    booking = _link_by_metadata(md["booking_id"])
                # 2) Fallback: client + service_code + booking_start
                if not booking:
                    booking = _link_by_client_and_time(
                        customer_id=customer_id,
                        service_code=svc_code or (md.get("service_code") or "").strip() or None,
                        booking_start=md.get("booking_start"),
                    )
                if booking:
                    was_updated = _update_booking_from_invoice(booking, inv, md)
                    if was_updated:
                        counts["updated"] += 1
                    counts["linked"] += 1
                else:
                    counts["unlinked"] += 1

            # Run validator to set requires_admin_review + review_diff if mismatches
            try:
                pre_flagged = Booking.objects.filter(requires_admin_review=True).count()
                validate_invoice_against_bookings(inv)
                post_flagged = Booking.objects.filter(requires_admin_review=True).count()
                if post_flagged > pre_flagged:
                    counts["flagged"] += (post_flagged - pre_flagged)
            except Exception as e:
                log.exception("Validator error for invoice %s: %s", getattr(inv, "id", None), e)
        except Exception as e:
            counts["errors"] += 1
            log.exception("Invoice sync error (id=%s): %s", getattr(inv, "id", None), e)
    log.info("Invoice sync complete: %s", counts)
    return counts


def process_invoice(inv) -> Dict[str, int]:
    """
    Process a single Stripe invoice object (as delivered by webhooks).
    Links line items to bookings, updates invoice fields, and runs validator.
    Returns a small counts dict.
    """
    counts = {"line_items": 0, "linked": 0, "updated": 0, "flagged": 0, "unlinked": 0, "errors": 0}
    try:
        customer_id = getattr(inv, "customer", None) or (inv.get("customer") if isinstance(inv, dict) else None)
        lines = getattr(inv, "lines", None) if not isinstance(inv, dict) else inv.get("lines")
        line_items = getattr(lines, "data", []) if lines and not isinstance(lines, dict) else ((lines or {}).get("data", []) if isinstance(lines, dict) else [])
        for li in (line_items or []):
            counts["line_items"] += 1
            md = getattr(li, "metadata", None) or (li.get("metadata") if isinstance(li, dict) else {}) or {}
            svc = _service_from_line(li, md)
            svc_code = getattr(svc, "code", None)
            booking = None
            if "booking_id" in md:
                booking = _link_by_metadata(md["booking_id"])
            if not booking:
                booking = _link_by_client_and_time(
                    customer_id=customer_id,
                    service_code=svc_code or (md.get("service_code") or "").strip() or None,
                    booking_start=md.get("booking_start"),
                )
            if booking:
                if _update_booking_from_invoice(booking, inv, md):
                    counts["updated"] += 1
                counts["linked"] += 1
            else:
                counts["unlinked"] += 1
        try:
            pre = Booking.objects.filter(requires_admin_review=True).count()
            validate_invoice_against_bookings(inv)
            post = Booking.objects.filter(requires_admin_review=True).count()
            if post > pre:
                counts["flagged"] += (post - pre)
        except Exception as e:
            log.exception("Validator error (invoice %s): %s", getattr(inv, "id", None), e)
    except Exception as e:
        counts["errors"] += 1
        log.exception("process_invoice error (id=%s): %s", getattr(inv, "id", None), e)
    return counts
