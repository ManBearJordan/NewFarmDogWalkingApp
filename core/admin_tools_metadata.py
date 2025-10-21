from datetime import datetime
from zoneinfo import ZoneInfo
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils.timezone import make_naive, is_aware
from django.urls import reverse
import logging
import stripe
from .models import Booking, Service, StripeSubscriptionSchedule, StripeSubscriptionLink

log = logging.getLogger(__name__)
BRISBANE = ZoneInfo("Australia/Brisbane")
KNOWN_KEYS = {"booking_id","booking_start","booking_end","dogs","location","service_code"}

def _parse_iso_local(dt_str: str):
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

def _diff_vs_booking(b: Booking, md: dict):
    diff = {}
    inv_start = _parse_iso_local(md.get("booking_start"))
    inv_end = _parse_iso_local(md.get("booking_end"))
    # Compare naive datetimes
    if inv_start:
        booking_start_naive = make_naive(b.start_dt, BRISBANE) if is_aware(b.start_dt) else b.start_dt
        if booking_start_naive != inv_start:
            diff["start_dt"] = {"booking": b.start_dt.isoformat(), "invoice": inv_start.isoformat()}
    if inv_end:
        booking_end_naive = make_naive(b.end_dt, BRISBANE) if is_aware(b.end_dt) else b.end_dt
        if booking_end_naive != inv_end:
            diff["end_dt"] = {"booking": b.end_dt.isoformat(), "invoice": inv_end.isoformat()}
    if "dogs" in md:
        try:
            inv_dogs = int(md["dogs"])
            if hasattr(b, "dogs") and b.dogs is not None and b.dogs != inv_dogs:
                diff["dogs"] = {"booking": b.dogs, "invoice": inv_dogs}
        except Exception:
            pass
    if "location" in md:
        inv_loc = (md.get("location") or "").strip()
        if hasattr(b, "location") and (b.location or "") != inv_loc:
            diff["location"] = {"booking": b.location or "", "invoice": inv_loc}
    if "service_code" in md and b.service and b.service.code:
        inv_svc = (md.get("service_code") or "").strip()
        if b.service.code != inv_svc:
            diff["service_code"] = {"booking": b.service.code, "invoice": inv_svc}
    return diff

@staff_member_required
def invoice_metadata(request, booking_id: int):
    """
    Displays the Stripe invoice line-item metadata relevant to this booking,
    highlights differences vs the booking, and shows our subscription schedule (if any).
    """
    b = get_object_or_404(Booking.objects.select_related("client","service"), id=booking_id)
    line_results = []
    invoice_id = b.stripe_invoice_id

    if not invoice_id:
        messages.info(request, "This booking has no Stripe invoice id attached.")
    else:
        try:
            inv = stripe.Invoice.retrieve(invoice_id, expand=["lines"])
            for li in (inv.lines.data or []):
                md = getattr(li, "metadata", None) or {}
                # Only show items mapped to this booking
                if str(md.get("booking_id") or "") != str(b.id):
                    continue
                diff = _diff_vs_booking(b, md)
                unknown = sorted(set(md.keys()) - KNOWN_KEYS)
                line_results.append({
                    "description": getattr(li, "description", ""),
                    "amount_total": getattr(li, "amount", None) or getattr(li, "amount_total", None),
                    "metadata": dict(md),
                    "diff": diff,
                    "unknown": unknown,
                })
        except Exception as e:
            log.exception("Failed to fetch invoice %s: %s", invoice_id, e)
            messages.error(request, f"Could not fetch invoice {invoice_id}: {e}")

    # Show any subscription schedule we maintain for this client/service
    sched = None
    if b.service and b.service.code:
        try:
            sub_link = StripeSubscriptionLink.objects.filter(
                client=b.client, service_code=b.service.code, active=True
            ).first()
            if sub_link:
                sched = StripeSubscriptionSchedule.objects.filter(sub=sub_link).first()
        except Exception:
            pass

    context = {
        "booking": b,
        "invoice_id": invoice_id,
        "line_results": line_results,
        "review_diff": b.review_diff or {},
        "sched": sched,
    }
    return render(request, "admin_tools/invoice_metadata.html", context)
