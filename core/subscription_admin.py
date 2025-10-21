from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from .models import StripeSubscriptionLink, StripeSubscriptionSchedule, Service
import datetime

@staff_member_required
def link_list(request):
    links = StripeSubscriptionLink.objects.select_related("client").order_by("client__name")
    services = Service.objects.filter(is_active=True)
    # Build a dictionary mapping subscription_id to schedule
    schedules = {}
    for sched in StripeSubscriptionSchedule.objects.select_related("sub").all():
        schedules[sched.sub.stripe_subscription_id] = sched
    return render(request, "admin_tools/sub_links.html", {
        "links": links, 
        "services": services,
        "schedules": schedules
    })

@staff_member_required
@require_http_methods(["POST"])
def link_save(request, link_id):
    l = StripeSubscriptionLink.objects.filter(id=link_id).first()
    if not l:
        messages.error(request, "Link not found.")
        return redirect("admin_sub_links")
    
    # Validate and set service_code
    service_code = request.POST.get("service_code")
    if service_code:
        if not Service.objects.filter(code=service_code, is_active=True).exists():
            messages.error(request, "Invalid service code.")
            return redirect("admin_sub_links")
        l.service_code = service_code
    else:
        l.service_code = None
    
    # Backward compatibility: validate and set weekday on link
    weekday_str = request.POST.get("weekday")
    if weekday_str:
        try:
            weekday_val = int(weekday_str)
            if 0 <= weekday_val <= 6:
                l.weekday = weekday_val
            else:
                messages.error(request, "Invalid weekday value.")
                return redirect("admin_sub_links")
        except (ValueError, TypeError):
            messages.error(request, "Invalid weekday value.")
            return redirect("admin_sub_links")
    else:
        l.weekday = None
    
    # Backward compatibility: validate and set time_of_day on link
    time_str = request.POST.get("time_of_day")
    if time_str:
        try:
            # Parse the time string to validate format and convert to time object
            time_obj = datetime.datetime.strptime(time_str, "%H:%M").time()
            l.time_of_day = time_obj
        except (ValueError, TypeError):
            messages.error(request, "Invalid time format. Use HH:MM.")
            return redirect("admin_sub_links")
    else:
        l.time_of_day = None
    
    # Save the link
    l.save()
    
    # Ensure schedule exists and update new fields
    sched, created = StripeSubscriptionSchedule.objects.get_or_create(
        sub=l,
        defaults={
            "weekdays_csv": "wed",
            "default_time": "10:30",
        }
    )
    
    # Update schedule fields from form (new pattern)
    days = request.POST.get("days") or None
    start_time = request.POST.get("start_time") or None
    location = request.POST.get("location") or None
    repeats = request.POST.get("repeats") or None
    
    # Validate repeats
    if repeats not in (StripeSubscriptionSchedule.REPEATS_WEEKLY, StripeSubscriptionSchedule.REPEATS_FORTNIGHTLY):
        repeats = StripeSubscriptionSchedule.REPEATS_WEEKLY
    
    # Update fields
    sched.days = days
    sched.start_time = start_time
    sched.location = location
    sched.repeats = repeats
    
    sched.save()
    
    messages.success(request, "Saved.")
    return redirect("admin_sub_links")
