from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Booking

@staff_member_required
def reconcile_list(request):
    # Bookings without invoice id
    no_invoice = Booking.objects.filter(stripe_invoice_id__isnull=True).order_by("-start_dt")[:50]
    # (extend here: invoices without bookings if you store a local invoice table)
    return render(request, "admin_tools/reconcile_list.html", {"no_invoice": no_invoice})

@staff_member_required
def reconcile_mark_paid(request, booking_id):
    b = Booking.objects.filter(id=booking_id).first()
    if not b:
        messages.error(request, "Booking not found.")
        return redirect("admin_reconcile")
    b.mark_paid()
    messages.success(request, f"Marked booking #{b.id} paid.")
    return redirect("admin_reconcile")
