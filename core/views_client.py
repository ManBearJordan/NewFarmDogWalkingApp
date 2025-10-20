from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from .models import Booking, Client, Service

def _linked_client(user):
    try:
        return Client.objects.get(user=user)
    except Client.DoesNotExist:
        return None

@login_required
def client_dashboard(request):
    client = _linked_client(request.user)
    if not client:
        messages.info(request, "Your login isn't linked to a client record yet. Please contact support.")
        upcoming = Booking.objects.none()
    else:
        upcoming = (Booking.objects
                    .filter(client=client, start_dt__gte=timezone.now())
                    .order_by("start_dt")[:10])
    return render(request, "portal/dashboard.html", {"upcoming": upcoming, "client": client})

@login_required
def client_calendar(request):
    client = _linked_client(request.user)
    if not client:
        messages.info(request, "Your login isn't linked to a client record yet.")
        return redirect("portal_home")
    # Keep it simple: same list, but separated page for future calendar widget
    upcoming = (Booking.objects
                .filter(client=client, start_dt__gte=timezone.now()-timedelta(days=1))
                .order_by("start_dt")[:50])
    return render(request, "portal/calendar.html", {"upcoming": upcoming})

@login_required
def booking_create(request):
    client = _linked_client(request.user)
    if not client:
        messages.error(request, "You need a linked client record to book.")
        return redirect("portal_home")
    services = Service.objects.filter(is_active=True, duration_minutes__isnull=False).order_by("name")
    if request.method == "POST":
        service_id = request.POST.get("service_id")
        start = request.POST.get("start")
        try:
            svc = Service.objects.get(id=service_id, is_active=True)
        except Service.DoesNotExist:
            messages.error(request, "Please choose a valid service.")
            return redirect("portal_booking_create")
        if not svc.duration_minutes:
            messages.error(request, "That service isn't fully configured yet.")
            return redirect("portal_booking_create")
        try:
            start_dt = datetime.fromisoformat(start)
        except Exception:
            messages.error(request, "Invalid start time.")
            return redirect("portal_booking_create")
        end_dt = start_dt + timedelta(minutes=svc.duration_minutes)
        # Store in session for confirm step
        request.session["pending_booking"] = {
            "service_id": svc.id,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
        }
        return redirect("portal_booking_confirm")
    return render(request, "portal/booking_create.html", {"services": services})

@login_required
def booking_confirm(request):
    client = _linked_client(request.user)
    if not client:
        messages.error(request, "You need a linked client record to book.")
        return redirect("portal_home")
    data = request.session.get("pending_booking")
    if not data:
        messages.info(request, "No booking in progress.")
        return redirect("portal_booking_create")
    svc = Service.objects.filter(id=data["service_id"]).first()
    start_dt = datetime.fromisoformat(data["start"])
    end_dt = datetime.fromisoformat(data["end"])
    if request.method == "POST":
        # Create booking (price/stripe link may be attached later)
        Booking.objects.create(
            client=client,
            service=svc,
            service_code=svc.code,
            service_name=svc.name,
            service_label=svc.name,
            start_dt=start_dt,
            end_dt=end_dt,
            price_cents=0,  # portal checkout can attach invoice later
            status="pending",
            location="",
            deleted=False,
        )
        request.session.pop("pending_booking", None)
        messages.success(request, "Booking created. We'll be in touch if anything changes.")
        return redirect("portal_home")
    return render(request, "portal/booking_confirm.html", {"service": svc, "start": start_dt, "end": end_dt})
