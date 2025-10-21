from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from .models import StripeSubscriptionLink, StripeSubscriptionSchedule, Service


def _get_or_create_schedule_for_link(link: StripeSubscriptionLink) -> StripeSubscriptionSchedule:
    """
    Get or create a schedule for a subscription link.
    Uses the OneToOne relationship via link.schedule or creates a new one.
    """
    try:
        sched = link.schedule
    except StripeSubscriptionSchedule.DoesNotExist:
        # Create a new schedule with defaults
        sched = StripeSubscriptionSchedule.objects.create(
            sub=link,
            weekdays_csv="wed",  # default fallback
            default_time="10:30",  # default fallback
            location="Home",
        )
    return sched


@staff_member_required
def subs_unscheduled(request):
    """
    List Stripe subscriptions that are missing a complete schedule.
    """
    rows = []
    links = StripeSubscriptionLink.objects.select_related("client").order_by("client__name", "stripe_subscription_id")
    for link in links:
        try:
            sched = link.schedule
        except StripeSubscriptionSchedule.DoesNotExist:
            sched = None
        
        status = "complete" if (sched and sched.is_complete()) else "needs schedule"
        rows.append({
            "link": link,
            "sched": sched,
            "status": status,
            "missing": [] if (sched and sched.is_complete()) else ((sched.missing_fields() if sched else ["service_code","days","start_time","location","repeats"])),
        })
    return render(request, "admin_tools/subs_unscheduled.html", {"rows": rows})


@staff_member_required
@transaction.atomic
def subs_wizard(request, link_id: int):
    """
    Capture service_code, days, start_time, repeats, location for a Stripe sub.
    """
    link = get_object_or_404(StripeSubscriptionLink.objects.select_related("client"), id=link_id)
    sched = _get_or_create_schedule_for_link(link)
    services = Service.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        service_code = (request.POST.get("service_code") or "").strip() or None
        days = (request.POST.get("days") or "").strip() or None
        start_time = (request.POST.get("start_time") or "").strip() or None
        repeats = (request.POST.get("repeats") or "").strip().lower() or "weekly"
        location = (request.POST.get("location") or "").strip() or "Home"

        # Update the link's service_code (this is where it's stored in current model)
        link.service_code = service_code or link.service_code
        link.save()

        # Update the schedule fields
        sched.days = days
        sched.start_time = start_time
        sched.repeats = repeats if repeats in (StripeSubscriptionSchedule.REPEATS_WEEKLY, StripeSubscriptionSchedule.REPEATS_FORTNIGHTLY) else StripeSubscriptionSchedule.REPEATS_WEEKLY
        sched.location = location
        
        try:
            sched.full_clean()
        except Exception as e:
            messages.error(request, f"Please fix the errors: {e}")
        else:
            sched.save()
            messages.success(request, "Subscription schedule saved.")
            return redirect("admin_subs_unscheduled")

    ctx = {
        "link": link,
        "sched": sched,
        "services": services,
        "repeats_choices": (
            (StripeSubscriptionSchedule.REPEATS_WEEKLY, "Weekly"),
            (StripeSubscriptionSchedule.REPEATS_FORTNIGHTLY, "Fortnightly"),
        ),
    }
    return render(request, "admin_tools/subs_wizard.html", ctx)
