from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from .models import StripeSubscriptionLink, Service
import datetime

@staff_member_required
def link_list(request):
    links = StripeSubscriptionLink.objects.order_by("client__name")
    services = Service.objects.filter(is_active=True)
    return render(request, "admin_tools/sub_links.html", {"links": links, "services": services})

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
    
    # Validate and set weekday
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
    
    # Validate and set time_of_day
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
    
    l.save()
    messages.success(request, "Saved.")
    return redirect("admin_sub_links")
