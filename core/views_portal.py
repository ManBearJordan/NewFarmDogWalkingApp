"""
Portal views for pre-pay booking flow with flexible capacity.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.utils import timezone
from django.conf import settings
from datetime import datetime, timedelta
from .models import Client, Booking, TimetableBlock
from .capacity_helpers import (
    list_blocks_for_date,
    block_remaining_capacity,
    create_hold,
    get_default_duration_minutes
)
from .stripe_integration import create_payment_intent, retrieve_payment_intent, cancel_payment_intent
from .tasks import send_booking_confirmation_email


def root_router(request):
    """
    Route the root URL based on authentication status.
    Authenticated users go to portal, unauthenticated to login.
    """
    if request.user.is_authenticated:
        # Clients land at portal; staff can use menu to reach /bookings/
        return HttpResponseRedirect('/portal/')
    return HttpResponseRedirect('/accounts/login/')


@login_required
def portal_booking_new(request):
    """Portal booking form."""
    try:
        client = request.user.client_profile
    except AttributeError:
        from django.contrib import messages
        messages.error(request, "Your login is not linked to a client profile.")
        return redirect("portal_home")
    
    if request.method == "GET":
        return render(
            request,
            "core/portal_booking_form.html",
            {
                "client": client,
                "STRIPE_PUBLISHABLE_KEY": getattr(settings, "STRIPE_PUBLISHABLE_KEY", None),
            },
        )
    return HttpResponseBadRequest("Method not allowed")


@login_required
def portal_blocks_for_date(request):
    """AJAX endpoint: given date + service_code, return blocks with remaining capacity."""
    date_str = request.GET.get("date")
    service_code = request.GET.get("service_code")
    
    if not date_str or not service_code:
        return JsonResponse({"error": "missing params"}, status=400)
    
    try:
        date = datetime.fromisoformat(date_str).date()
    except ValueError:
        return JsonResponse({"error": "invalid date"}, status=400)
    
    items = []
    for blk in list_blocks_for_date(date):
        remaining = block_remaining_capacity(blk, service_code)
        items.append({
            "id": blk.id,
            "label": blk.label or f"{blk.start_time}–{blk.end_time}",
            "start": str(blk.start_time),
            "end": str(blk.end_time),
            "remaining": remaining,
        })
    
    return JsonResponse({"blocks": items})


@login_required
def portal_checkout_start(request):
    """
    1) Client picks date, block, service. We check remaining capacity and place a short-lived hold.
    2) Create a PaymentIntent and return its client_secret for Stripe.js.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")
    
    try:
        client = request.user.client_profile
    except AttributeError:
        return JsonResponse({"error": "No client profile linked."}, status=403)
    
    service_code = request.POST.get("service_code")
    block_id = request.POST.get("block_id")
    price_cents = int(request.POST.get("price_cents") or 0)
    
    blk = get_object_or_404(TimetableBlock, id=block_id)
    
    if block_remaining_capacity(blk, service_code) <= 0:
        return JsonResponse({"error": "That time is fully booked."}, status=409)
    
    hold = create_hold(blk, service_code, client)
    intent = create_payment_intent(
        amount_cents=price_cents,
        customer_id=client.stripe_customer_id,
        metadata={
            "client_id": client.id,
            "service_code": service_code,
            "block_id": blk.id,
            "hold": str(hold.token)
        },
        receipt_email=client.email or None,
    )
    
    return JsonResponse({
        "client_secret": intent.client_secret,
        "hold_token": str(hold.token)
    })


@login_required
def portal_checkout_finalize(request):
    """
    Called after Stripe.js confirms the PaymentIntent on the client side.
    We re-check capacity (hold covers races), then create the booking and return a confirmation URL.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")
    
    try:
        client = request.user.client_profile
    except AttributeError:
        return JsonResponse({"error": "No client profile linked."}, status=403)
    
    hold_token = request.POST.get("hold_token")
    pi_id = request.POST.get("payment_intent_id")
    service_code = request.POST.get("service_code")
    block_id = int(request.POST.get("block_id"))
    price_cents = int(request.POST.get("price_cents") or 0)
    
    blk = get_object_or_404(TimetableBlock, id=block_id)
    
    # Re-check remaining capacity (holds + bookings counted)
    if block_remaining_capacity(blk, service_code) <= 0:
        cancel_payment_intent(pi_id)
        return JsonResponse({"error": "Capacity just ran out. Your payment was not captured."}, status=409)
    
    # Fetch PaymentIntent to get the Charge id (for admin linking / refunds)
    pi = retrieve_payment_intent(pi_id)
    charge_id = None
    if getattr(pi, "latest_charge", None):
        charge_id = pi.latest_charge
    
    # Create booking now (no Stripe invoice for portal path)
    # Compute start/end from block + default duration
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(blk.date, blk.start_time), tz)
    dur = get_default_duration_minutes(service_code)
    end_candidate = timezone.make_aware(datetime.combine(blk.date, blk.end_time), tz)
    end_dt = min(start_dt + timedelta(minutes=dur), end_candidate)
    
    b = Booking.objects.create(
        client=client,
        service_code=service_code,
        service_name=service_code.title(),
        service_label=service_code.title(),
        block_label=blk.label,
        start_dt=start_dt,
        end_dt=end_dt,
        price_cents=price_cents,
        status="active",
        deleted=False,
        stripe_invoice_id=None,  # portal flow does NOT create invoices
        payment_intent_id=pi_id,
        charge_id=charge_id,
        location="",
        notes="",
    )
    
    # Fire-and-forget confirmation email (runs on Celery worker if available)
    try:
        send_booking_confirmation_email.delay(b.id)
    except Exception:
        # If Celery isn't running, don't block the request; you can still send later or rely on Stripe receipt
        pass
    
    return JsonResponse({"ok": True, "booking_id": b.id, "redirect": "/portal/bookings/confirm/"})
