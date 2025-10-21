from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from zoneinfo import ZoneInfo

import stripe
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import transaction
from django.utils.timezone import make_naive, is_aware, localtime

from .models import Booking, Client, Service
from .stripe_invoices_sync import process_invoice

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

def _recent_invoices(days: int = 60) -> List[Any]:
    since = datetime.now(tz=BRISBANE) - timedelta(days=days)
    starting_after = None
    out = []
    while True:
        params = {
            "limit": 100,
            "created": {"gte": int(since.timestamp())},
            "expand": ["data.lines.data"],
        }
        if starting_after:
            params["starting_after"] = starting_after
        page = stripe.Invoice.list(**params)
        data = getattr(page, "data", []) or []
        out.extend(data)
        if not getattr(page, "has_more", False):
            break
        starting_after = data[-1].id if data else None
    return out

def _line_items(inv) -> List[Any]:
    lines = getattr(inv, "lines", None)
    return getattr(lines, "data", []) if lines else []

def _booking_by_id(val) -> Optional[Booking]:
    try:
        bid = int(str(val))
    except Exception:
        return None
    return Booking.objects.filter(id=bid).first()

def _client_by_customer_id(customer_id: Optional[str]) -> Optional[Client]:
    if not customer_id:
        return None
    return Client.objects.filter(stripe_customer_id=customer_id).first()

def _summarize_invoices_for_reconcile(days: int = 60):
    """
    Return a list of invoices with only the lines that are 'unlinked' from local bookings
    (i.e., no local booking has this invoice id, or metadata.booking_id doesn't match a booking).
    """
    try:
        invoices = _recent_invoices(days=days)
    except Exception as e:
        log.warning("Failed to fetch Stripe invoices: %s", e)
        return []
    unlinked = []
    for inv in invoices:
        inv_id = getattr(inv, "id", None)
        status = getattr(inv, "status", None)
        customer = getattr(inv, "customer", None)
        lines = []
        for li in _line_items(inv):
            md = getattr(li, "metadata", None) or {}
            li_id = getattr(li, "id", None)
            bid = md.get("booking_id")
            b = _booking_by_id(bid) if bid else None
            # Consider a line 'linked' if a local booking explicitly references this invoice
            is_linked_locally = Booking.objects.filter(stripe_invoice_id=inv_id).exists()
            if b is None and not is_linked_locally:
                # show this line as unlinked candidate
                lines.append({
                    "line_id": li_id,
                    "description": getattr(li, "description", "") or "",
                    "amount_total": getattr(li, "amount", None) or getattr(li, "amount_total", None),
                    "metadata": dict(md),
                })
        if lines:
            unlinked.append({
                "invoice_id": inv_id,
                "status": status,
                "customer_id": customer,
                "hosted_invoice_url": getattr(inv, "hosted_invoice_url", None) or getattr(inv, "invoice_pdf", None),
                "lines": lines,
            })
    return unlinked

def _summarize_unlinked_bookings(days: int = 60):
    """
    Local bookings with no stripe_invoice_id within the window (past 30 / next 30 by default).
    """
    now = localtime()
    start = now - timedelta(days=days//2)
    end = now + timedelta(days=days//2)
    qs = Booking.objects.filter(stripe_invoice_id__isnull=True, start_dt__gte=start, start_dt__lte=end).select_related("client", "service").order_by("start_dt")
    return qs

@staff_member_required
def reconcile_index(request):
    try:
        days = int(request.GET.get("days", "60"))
    except Exception:
        days = 60
    ctx = {
        "days": days,
        "unlinked_invoices": _summarize_invoices_for_reconcile(days=days),
        "unlinked_bookings": _summarize_unlinked_bookings(days=days),
    }
    return render(request, "admin_tools/reconcile.html", ctx)

def _update_invoice_fields_from_obj(booking: Booking, inv) -> bool:
    changed = False
    inv_id = getattr(inv, "id", None)
    inv_status = getattr(inv, "status", None)
    inv_pdf = getattr(inv, "invoice_pdf", None) or getattr(inv, "hosted_invoice_url", None)
    paid_ts = getattr(getattr(inv, "status_transitions", None), "paid_at", None)
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
    if inv_status == "paid" and paid_at and booking.paid_at != paid_at:
        booking.paid_at = paid_at
        changed = True
    if changed:
        booking.save(update_fields=["stripe_invoice_id","stripe_invoice_status","invoice_pdf_url","paid_at"])
    return changed

@staff_member_required
@require_POST
@transaction.atomic
def reconcile_link(request):
    """
    Link a local booking to a specific Stripe invoice (and implicitly the selected line).
    """
    booking_id = request.POST.get("booking_id")
    invoice_id = request.POST.get("invoice_id")
    if not (booking_id and invoice_id):
        messages.error(request, "booking_id and invoice_id are required.")
        return redirect("admin_reconcile")
    b = get_object_or_404(Booking, id=booking_id)
    try:
        inv = stripe.Invoice.retrieve(invoice_id, expand=["lines.data"])
    except Exception as e:
        messages.error(request, f"Stripe error retrieving invoice {invoice_id}: {e}")
        return redirect("admin_reconcile")
    _update_invoice_fields_from_obj(b, inv)
    # Re-run the PR9 processor to set review flags if needed
    try:
        process_invoice(inv)
    except Exception as e:
        log.exception("process_invoice failed during manual link: %s", e)
    messages.success(request, f"Linked booking #{b.id} to invoice {invoice_id}.")
    return redirect("admin_reconcile")

@staff_member_required
@require_POST
@transaction.atomic
def reconcile_detach(request):
    """
    Detach invoice linkage from a booking (local only).
    """
    booking_id = request.POST.get("booking_id")
    b = get_object_or_404(Booking, id=booking_id)
    b.stripe_invoice_id = None
    b.stripe_invoice_status = None
    b.invoice_pdf_url = None
    # do not clear paid_at to preserve history; detach only means unlink
    b.save(update_fields=["stripe_invoice_id","stripe_invoice_status","invoice_pdf_url"])
    messages.info(request, f"Detached invoice from booking #{b.id}.")
    return redirect("admin_reconcile")

@staff_member_required
@require_POST
@transaction.atomic
def reconcile_create_from_line(request):
    """
    Create a Booking from a Stripe invoice line metadata.
    Requirements:
      - Stripe customer must map to a local Client
      - metadata must contain service_code and booking_start (ISO local)
      - Service must have duration_minutes
    """
    invoice_id = request.POST.get("invoice_id")
    line_id = request.POST.get("line_id")
    if not (invoice_id and line_id):
        messages.error(request, "invoice_id and line_id are required.")
        return redirect("admin_reconcile")
    try:
        inv = stripe.Invoice.retrieve(invoice_id, expand=["lines.data"])
    except Exception as e:
        messages.error(request, f"Stripe error retrieving invoice {invoice_id}: {e}")
        return redirect("admin_reconcile")
    customer_id = getattr(inv, "customer", None)
    client = _client_by_customer_id(customer_id)
    if not client:
        messages.error(request, "No local Client matches this Stripe customer.")
        return redirect("admin_reconcile")
    target_line = None
    for li in _line_items(inv):
        if getattr(li, "id", None) == line_id:
            target_line = li
            break
    if not target_line:
        messages.error(request, f"Invoice line {line_id} not found.")
        return redirect("admin_reconcile")
    md = getattr(target_line, "metadata", None) or {}
    service_code = (md.get("service_code") or "").strip()
    start_dt = _parse_iso_local(md.get("booking_start"))
    if not (service_code and start_dt):
        messages.error(request, "Line metadata must include service_code and booking_start.")
        return redirect("admin_reconcile")
    service = Service.objects.filter(code=service_code, is_active=True).first()
    if not (service and service.duration_minutes):
        messages.error(request, "Service missing or has no duration; cannot compute end time.")
        return redirect("admin_reconcile")
    end_dt = start_dt + timedelta(minutes=service.duration_minutes)
    # Avoid duplicates
    exists = Booking.objects.filter(client=client, service=service, start_dt=start_dt).exists()
    if exists:
        messages.info(request, "A booking already exists at that slot; no new booking created.")
        return redirect("admin_reconcile")
    # Create manual (non-autogenerated) booking
    b = Booking.objects.create(
        client=client,
        service=service,
        start_dt=start_dt,
        end_dt=end_dt,
        price_cents=0,
        status="pending",
        location=md.get("location") or "Home",
        autogenerated=False,
        service_code=service.code,
        service_name=service.name,
        service_label=service.name,
    )
    # Link it to the invoice we created it from
    _update_invoice_fields_from_obj(b, inv)
    # Re-run processor to set review flags if mismatches
    try:
        process_invoice(inv)
    except Exception as e:
        log.exception("process_invoice failed after create_from_line: %s", e)
    messages.success(request, f"Created booking #{b.id} from invoice line and linked.")
    return redirect("admin_reconcile")
