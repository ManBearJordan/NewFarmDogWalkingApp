from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.forms import modelformset_factory
from .models import Service
from .forms import ServiceDurationForm


@staff_member_required
def service_settings(request):
    """
    Staff page to set service durations.
    Seeds three common services on first visit if none exist.
    """
    if Service.objects.count() == 0:
        Service.objects.bulk_create([
            Service(code="walk30", name="Standard Walk (30m)"),
            Service(code="walk60", name="Extended Walk (60m)"),
            Service(code="puppy30", name="Puppy Visit (30m)"),
        ])

    FormSet = modelformset_factory(Service, form=ServiceDurationForm, can_delete=False, extra=0)

    if request.method == "POST":
        formset = FormSet(request.POST, queryset=Service.objects.order_by("name"))
        if formset.is_valid():
            formset.save()
            messages.success(request, "Service durations saved.")
            return redirect("service_settings")
    else:
        formset = FormSet(queryset=Service.objects.order_by("name"))

    missing = Service.objects.filter(is_active=True, duration_minutes__isnull=True)
    return render(request, "core/settings_services.html", {
        "formset": formset,
        "missing": missing.exists(),
    })
