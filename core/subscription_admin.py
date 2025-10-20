from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import StripeSubscriptionLink, Service

@staff_member_required
def link_list(request):
    links = StripeSubscriptionLink.objects.order_by("client__name")
    services = Service.objects.filter(is_active=True)
    return render(request, "admin_tools/sub_links.html", {"links": links, "services": services})

@staff_member_required
def link_save(request, link_id):
    l = StripeSubscriptionLink.objects.filter(id=link_id).first()
    if not l:
        messages.error(request, "Link not found.")
        return redirect("admin_sub_links")
    l.service_code = request.POST.get("service_code") or None
    l.weekday = int(request.POST.get("weekday")) if request.POST.get("weekday") != "" else None
    l.time_of_day = request.POST.get("time_of_day") or None
    l.save()
    messages.success(request, "Saved.")
    return redirect("admin_sub_links")
