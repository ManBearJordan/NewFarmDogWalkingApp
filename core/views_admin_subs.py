from datetime import datetime
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db import transaction
from .models import StripeSubscriptionLink, StripeSubscriptionSchedule, SubOccurrence, Booking, Client
from .capacity_helpers import get_default_duration_minutes

@staff_member_required
def subs_dashboard(request):
    """
    Shows: (1) Stripe subs without a schedule, to configure weekdays/time once.
           (2) Upcoming occurrences within N days that don't yet have a Booking -> assign a time/block to create booking.
    """
    no_sched = StripeSubscriptionLink.objects.filter(schedule__isnull=True).select_related("client")
    upcoming = SubOccurrence.objects.filter(active=True, start_dt__gte=timezone.now()).order_by("start_dt")[:200]
    # Filter to those without a booking
    # (You may also maintain a fk from Booking to SubOccurrence; if you have it, adjust here)
    return render(request, "core/admin_subs_dashboard.html", {"no_sched": no_sched, "upcoming": upcoming})

@staff_member_required
def subs_set_schedule(request, sub_id):
    link = get_object_or_404(StripeSubscriptionLink, stripe_subscription_id=sub_id)
    if request.method == "POST":
        weekdays_csv = (request.POST.get("weekdays_csv") or "").strip().lower()
        default_time = (request.POST.get("default_time") or "").strip()
        dur = int((request.POST.get("duration") or 60))
        label = (request.POST.get("block_label") or "").strip() or None
        StripeSubscriptionSchedule.objects.update_or_create(
            sub=link,
            defaults={"weekdays_csv": weekdays_csv, "default_time": default_time, "default_duration_minutes": dur, "default_block_label": label},
        )
        from .stripe_subscriptions import materialize_future_holds
        materialize_future_holds(link, horizon_days=30)
        return redirect("admin_subs_dashboard")
    return render(request, "core/admin_subs_set_schedule.html", {"link": link})

@staff_member_required
def subs_finalize_occurrence(request, occ_id):
    """
    You select a specific time for an occurrence day and we create the Booking.
    """
    occ = get_object_or_404(SubOccurrence, id=occ_id, active=True)
    link = get_object_or_404(StripeSubscriptionLink, stripe_subscription_id=occ.stripe_subscription_id)
    client = link.client
    if request.method == "POST":
        hhmm = (request.POST.get("start_time") or "").strip()
        hh, mm = [int(x) for x in hhmm.split(":")]
        start = timezone.make_aware(datetime(occ.start_dt.year, occ.start_dt.month, occ.start_dt.day, hh, mm), timezone.get_current_timezone())
        dur = get_default_duration_minutes(link.service_code)
        end = start + timezone.timedelta(minutes=dur)
        Booking.objects.create(
            client=client,
            service_code=link.service_code,
            service_name=link.service_code.title(),
            service_label=link.service_code.title(),
            block_label=None,
            start_dt=start,
            end_dt=end,
            location=client.address,
            price_cents=0,  # usually covered by subscription/invoice
            status="active",
            deleted=False,
            stripe_invoice_id=None,
        )
        return redirect("admin_subs_dashboard")
    return render(request, "core/admin_subs_finalize_occurrence.html", {"occ": occ, "link": link})
