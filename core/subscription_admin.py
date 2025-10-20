from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from .models import StripeSubscriptionLink, Service

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
    l.service_code = request.POST.get("service_code") or None
    
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
    
    l.time_of_day = request.POST.get("time_of_day") or None
    l.save()
    messages.success(request, "Saved.")
    return redirect("admin_sub_links")
