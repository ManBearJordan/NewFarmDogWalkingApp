from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages
from datetime import datetime
from zoneinfo import ZoneInfo
from django.utils import timezone as django_tz
from .models import Booking, Service

BRISBANE = ZoneInfo("Australia/Brisbane")


def _parse_iso_local(s: str):
    """Parse ISO datetime string and convert to timezone-aware datetime in Brisbane."""
    if not s:
        return None
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None
    if dt.tzinfo:
        # Convert to Brisbane time
        return dt.astimezone(BRISBANE)
    # If naive, assume it's already in Brisbane timezone and make it aware
    return django_tz.make_aware(dt, BRISBANE)


@staff_member_required
def review_list(request):
    """Display list of bookings requiring admin review."""
    qs = Booking.objects.filter(requires_admin_review=True).select_related("client", "service").order_by("-start_dt")
    return render(request, "admin_tools/review_list.html", {"bookings": qs})


@staff_member_required
@require_POST
def review_apply(request, booking_id: int):
    """Apply invoice metadata values to the booking."""
    b = get_object_or_404(Booking, id=booking_id)
    diff = b.review_diff or {}
    changed = []
    
    if "start_dt" in diff:
        dt = _parse_iso_local(diff["start_dt"]["invoice"])
        if dt:
            b.start_dt = dt
            changed.append("start_dt")
    
    if "end_dt" in diff:
        dt = _parse_iso_local(diff["end_dt"]["invoice"])
        if dt:
            b.end_dt = dt
            changed.append("end_dt")
    
    if "dogs" in diff:
        b.dogs = int(diff["dogs"]["invoice"])
        changed.append("dogs")
    
    if "location" in diff:
        b.location = diff["location"]["invoice"]
        changed.append("location")
    
    if "service_code" in diff:
        svc = Service.objects.filter(code=diff["service_code"]["invoice"]).first()
        if svc:
            b.service = svc
            b.service_code = svc.code
            changed.append("service")
    
    b.clear_review()
    if changed:
        b.save()
        messages.success(request, f"Applied {', '.join(changed)} to booking #{b.id}.")
    else:
        messages.info(request, "No applicable changes.")
    
    return redirect("admin_review_list")


@staff_member_required
@require_POST
def review_dismiss(request, booking_id: int):
    """Dismiss the review without applying changes."""
    b = get_object_or_404(Booking, id=booking_id)
    b.clear_review()
    messages.info(request, f"Dismissed review for booking #{b.id}.")
    return redirect("admin_review_list")
