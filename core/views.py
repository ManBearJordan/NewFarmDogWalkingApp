"""
Web views for the NewFarm Dog Walking App.

Provides simple views for client management and booking creation.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.http import urlencode
from django.utils.safestring import mark_safe
from django.forms import ModelForm
from datetime import datetime
from zoneinfo import ZoneInfo
from django.db.models import Q
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from datetime import datetime, date
from calendar import Calendar, monthrange
from django.views.decorators.http import require_http_methods
import json

from .models import Client, Booking, AdminEvent, SubOccurrence, Pet, BookingPet, Tag
from .forms import PetForm, ClientForm
from .booking_create_service import create_bookings_with_billing
from .stripe_integration import (
    ensure_customer,
    list_booking_services,
    get_invoice_dashboard_url,
    list_recent_invoices,
    get_customer_dashboard_url,
)
from .credit import add_client_credit
from .booking_filters import filter_active_bookings
from .ics_export import bookings_to_ics
from .date_range_helpers import parse_label, TZ, list_presets
from .subscription_sync import sync_subscriptions_to_bookings_and_calendar
from .unified_booking_helpers import get_canonical_service_info
from .unified_booking_helpers import create_booking_with_unified_fields
from .booking_create_service import create_bookings_from_rows
from .stripe_integration import get_invoice_public_url
from .admin_views import stripe_diagnostics_view


def client_list(request):
    """List clients and handle client creation."""
    if request.method == 'POST':
        # Create new client
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        notes = request.POST.get('notes', '').strip()
        
        if name and email:
            client = Client.objects.create(
                name=name,
                email=email,
                phone=phone,
                address=address,
                notes=notes,
                status='active'
            )
            messages.success(request, f'Client "{client.name}" created successfully.')
            return redirect('client_list')
        else:
            messages.error(request, 'Name and email are required.')
    
    clients = Client.objects.filter(status='active').order_by('name')
    # Pass cents values directly to template
    
    return render(request, 'core/client_list.html', {
        'clients': clients
    })


def client_create(request: HttpRequest) -> HttpResponse:
    """Create a client with tags support."""
    form = ClientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Client created.")
        return redirect("client_list")
    return render(request, "core/client_create.html", {"form": form})

# -----------------------------
# Clients: Stripe + Credit actions
# -----------------------------
@login_required
def clients_stripe_sync(request: HttpRequest) -> HttpResponse:
    """
    Link clients to Stripe customers by email (case-insensitive).
    Updates phone/address and saves stripe_customer_id on match/create.
    """
    from .models import Client
    if request.method != "POST":
        return redirect("client_list")
    updated = 0
    failed = 0
    qs = Client.objects.all()
    for c in qs:
        try:
            if c.email:
                sid = ensure_customer(c)
                if sid and c.stripe_customer_id != sid:
                    c.stripe_customer_id = sid
                    c.save(update_fields=["stripe_customer_id"])
                    updated += 1
        except Exception as e:
            failed += 1
    messages.success(request, f"Stripe customer sync complete. Linked/updated: {updated}. Errors: {failed}.")
    return redirect("client_list")


@login_required
def client_stripe_link(request: HttpRequest, client_id: int) -> HttpResponse:
    """
    Link a single client to Stripe by explicit input (cus_… or email).
    """
    from .models import Client
    c = get_object_or_404(Client, id=client_id)
    if request.method != "POST":
        return redirect("client_list")
    value = (request.POST.get("stripe_id_or_email") or "").strip()
    if not value:
        messages.error(request, "Enter a Stripe customer ID or email.")
        return redirect("client_list")
    try:
        if value.lower().startswith("cus_"):
            c.stripe_customer_id = value
            c.save(update_fields=["stripe_customer_id"])
            messages.success(request, f"Linked to {value}.")
        else:
            # treat as email
            c.email = value
            sid = ensure_customer(c)
            c.stripe_customer_id = sid
            c.save(update_fields=["email", "stripe_customer_id"])
            messages.success(request, f"Linked via email → {sid}.")
    except Exception as e:
        messages.error(request, f"Link failed: {e}")
    return redirect("client_list")


@login_required
def client_stripe_open(request: HttpRequest, client_id: int) -> HttpResponse:
    from .models import Client
    c = get_object_or_404(Client, id=client_id)
    if not c.stripe_customer_id:
        messages.warning(request, "This client is not linked to Stripe.")
        return redirect("client_list")
    url = get_customer_dashboard_url(c.stripe_customer_id)
    return HttpResponseRedirect(url)


@login_required
def client_credit_add(request: HttpRequest, client_id: int) -> HttpResponse:
    from .models import Client
    c = get_object_or_404(Client, id=client_id)
    if request.method != "POST":
        return redirect("client_list")
    try:
        # Accept cents ("2500"), dollars ("25.00"), or negative adjustments (e.g., "-1000") by opt-in flag.
        raw = (request.POST.get("amount") or "").strip()
        allow_negative = request.POST.get("allow_negative") == "1"
        if not raw:
            raise ValueError("Amount required")
        # parse to cents
        if raw.lstrip("-").isdigit():
            cents = int(raw)  # may be negative
        else:
            cents = int(round(float(raw) * 100))
        new_bal = add_client_credit(c, cents, allow_negative=allow_negative, reason="manual-adjust")
        messages.success(request, f"Credit updated. New balance: ${new_bal/100:.2f}")
    except Exception as e:
        messages.error(request, f"Failed to update credit: {e}")
    return redirect("client_list")


def booking_create_batch(request):
    """Create multiple bookings with billing."""
    if request.method == 'POST':
        try:
            # Get client
            client_id = request.POST.get('client_id')
            if not client_id:
                messages.error(request, 'Client selection is required.')
                return redirect('booking_create_batch')
            
            client = get_object_or_404(Client, id=client_id)
            
            # Parse booking rows from form data
            rows = []
            row_count = int(request.POST.get('row_count', 0))
            
            for i in range(row_count):
                service_label = request.POST.get(f'service_label_{i}', '').strip()
                start_dt_str = request.POST.get(f'start_dt_{i}', '').strip()
                end_dt_str = request.POST.get(f'end_dt_{i}', '').strip()
                location = request.POST.get(f'location_{i}', '').strip()
                dogs_str = request.POST.get(f'dogs_{i}', '1').strip()
                price_cents_str = request.POST.get(f'price_cents_{i}', '0').strip()
                notes = request.POST.get(f'notes_{i}', '').strip()
                
                # Skip empty rows
                if not service_label or not start_dt_str or not end_dt_str:
                    continue
                
                # Parse datetime fields
                try:
                    start_dt = datetime.fromisoformat(start_dt_str.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end_dt_str.replace('Z', '+00:00'))
                    if timezone.is_naive(start_dt):
                        start_dt = timezone.make_aware(start_dt)
                    if timezone.is_naive(end_dt):
                        end_dt = timezone.make_aware(end_dt)
                except ValueError as e:
                    messages.error(request, f'Invalid datetime format in row {i+1}: {e}')
                    return redirect('booking_create_batch')
                
                # Parse numeric fields
                try:
                    dogs = int(dogs_str) if dogs_str else 1
                    price_cents = int(price_cents_str) if price_cents_str else 0
                except ValueError:
                    messages.error(request, f'Invalid number format in row {i+1}')
                    return redirect('booking_create_batch')
                
                rows.append({
                    'service_label': service_label,
                    'start_dt': start_dt,
                    'end_dt': end_dt,
                    'location': location,
                    'dogs': dogs,
                    'price_cents': price_cents,
                    'notes': notes
                })
            
            if not rows:
                messages.error(request, 'At least one booking row is required.')
                return redirect('booking_create_batch')
            
            # Create bookings with billing
            result = create_bookings_with_billing(client, rows)
            
            # Get invoice URL if needed
            invoice_url = None
            if result.get('invoice_id'):
                try:
                    invoice_url = open_invoice_smart(result['invoice_id'])
                except Exception as e:
                    # Don't fail the entire process if invoice URL fails
                    print(f"Warning: Could not get invoice URL: {e}")
            
            # Pass cents values directly to template - let money filter handle formatting
            created_bookings = Booking.objects.filter(id__in=result.get('created_ids', [])).order_by('start_dt')
            
            return render(request, 'core/booking_batch_result.html', {
                'result': result,
                'client': client,
                'invoice_url': invoice_url,
                'total_credit_used_cents': result['total_credit_used'],
                'created_bookings': created_bookings
            })
            
        except Exception as e:
            messages.error(request, f'Error creating bookings: {e}')
            return redirect('booking_create_batch')
    
    # GET request - show form
    clients = Client.objects.filter(status='active').order_by('name')
    # Pass cents values directly to template
    
    services = list_booking_services()
    
    return render(request, 'core/booking_create_batch.html', {
        'clients': clients,
        'services': services,
        'services_json': json.dumps(services)
    })


@require_POST
def client_add_credit(request, client_id):
    """Add credit to a client account."""
    client = get_object_or_404(Client, id=client_id)
    
    try:
        credit_amount = request.POST.get('credit_amount', '0').strip()
        credit_cents = int(float(credit_amount) * 100)  # Convert dollars to cents
        
        if credit_cents <= 0:
            return JsonResponse({'error': 'Credit amount must be positive'}, status=400)
        
        # Add credit to client
        client.credit_cents += credit_cents
        client.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Added ${credit_amount} credit to {client.name}',
            'new_balance_cents': client.credit_cents,
            'new_balance_aud': client.credit_cents / 100.0
        })
        
    except (ValueError, TypeError) as e:
        return JsonResponse({'error': f'Invalid credit amount: {e}'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error adding credit: {e}'}, status=500)


def calendar_view(request):
    """Show calendar month view with day details."""
    # Get current month or requested month
    now = timezone.now()
    year = int(request.GET.get('year', now.year))
    month = int(request.GET.get('month', now.month))
    selected_date = request.GET.get('date')
    
    # Get calendar data for the month
    cal = Calendar(6)  # Start week on Sunday (6)
    month_days = cal.monthdayscalendar(year, month)
    
    # Prepare day data with counts
    days_data = {}
    calendar_days = {}  # day number -> data for easier template access
    
    # Get all relevant data for the month
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1)
    else:
        month_end = date(year, month + 1, 1)
    
    # Count bookings (exclude deleted and cancelled/voided status)
    bookings = filter_active_bookings(Booking.objects.filter(
        start_dt__date__gte=month_start,
        start_dt__date__lt=month_end,
    ))
    
    # Count SubOccurrences where active=True
    sub_occurrences = SubOccurrence.objects.filter(
        start_dt__date__gte=month_start,
        start_dt__date__lt=month_end,
        active=True
    )
    
    # Count AdminEvents
    admin_events = AdminEvent.objects.filter(
        due_dt__date__gte=month_start,
        due_dt__date__lt=month_end
    )
    
    # Build day counts
    for booking in bookings:
        day_key = booking.start_dt.date()
        day_num = day_key.day
        if day_num not in calendar_days:
            calendar_days[day_num] = {'bookings': 0, 'sub_occurrences': 0, 'admin_events': 0}
        calendar_days[day_num]['bookings'] += 1
    
    for sub_occurrence in sub_occurrences:
        day_key = sub_occurrence.start_dt.date()
        day_num = day_key.day
        if day_num not in calendar_days:
            calendar_days[day_num] = {'bookings': 0, 'sub_occurrences': 0, 'admin_events': 0}
        calendar_days[day_num]['sub_occurrences'] += 1
    
    for admin_event in admin_events:
        day_key = admin_event.due_dt.date()
        day_num = day_key.day
        if day_num not in calendar_days:
            calendar_days[day_num] = {'bookings': 0, 'sub_occurrences': 0, 'admin_events': 0}
        calendar_days[day_num]['admin_events'] += 1
    
    # Get bookings for selected date if provided
    selected_bookings = []
    if selected_date:
        try:
            selected_dt = datetime.strptime(selected_date, '%Y-%m-%d').date()
            selected_bookings = filter_active_bookings(Booking.objects.filter(
                start_dt__date=selected_dt,
            )).order_by('start_dt')
        except ValueError:
            pass
    
    # Month navigation
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    context = {
        'year': year,
        'month': month,
        'month_name': date(year, month, 1).strftime('%B %Y'),
        'month_days': month_days,
        'calendar_days': calendar_days,
        'selected_date': selected_date,
        'selected_bookings': selected_bookings,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
    }
    
    return render(request, 'core/calendar.html', context)


def reports_invoices_list(request):
    """List recent invoices for clients in our database."""
    from datetime import datetime
    
    # Get limit from query parameter, default to 20
    limit = min(int(request.GET.get('limit', 20)), 100)  # Cap at 100
    
    # Get recent invoices
    invoices = list_recent_invoices(limit=limit)
    
    # Convert amounts to AUD and add Stripe URLs
    for invoice in invoices:
        invoice['amount_aud'] = invoice['amount_cents'] / 100.0
        # Convert Unix timestamp to datetime object for template
        invoice['created_datetime'] = datetime.fromtimestamp(invoice['created'])
        try:
            invoice['stripe_url'] = open_invoice_smart(invoice['id'])
        except Exception:
            # If we can't generate URL (e.g. no API key), don't include it
            invoice['stripe_url'] = None
    
    return render(request, 'core/reports_invoices_list.html', {
        'invoices': invoices,
        'limit': limit
    })


#
# Pets — CRUD UI
#
class PetListView(LoginRequiredMixin, ListView):
    template_name = "core/pet_list.html"
    model = Pet
    context_object_name = "pets"
    paginate_by = 20

    def get_queryset(self):
        qs = Pet.objects.select_related("client").order_by("client__name", "name")
        q = (self.request.GET.get("q") or "").strip()
        client_id = (self.request.GET.get("client") or "").strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(species__icontains=q)
                | Q(breed__icontains=q)
                | Q(medications__icontains=q)
                | Q(behaviour__icontains=q)
                | Q(client__name__icontains=q)
            )
        if client_id:
            qs = qs.filter(client_id=client_id)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = (self.request.GET.get("q") or "").strip()
        ctx["client_filter"] = (self.request.GET.get("client") or "").strip()
        ctx["clients"] = Client.objects.order_by("name")
        return ctx


class PetCreateView(LoginRequiredMixin, CreateView):
    model = Pet
    form_class = PetForm
    template_name = "core/pet_form.html"
    success_url = reverse_lazy("pet_list")

    def form_valid(self, form):
        messages.success(self.request, "Pet created.")
        return super().form_valid(form)


class PetUpdateView(LoginRequiredMixin, UpdateView):
    model = Pet
    form_class = PetForm
    template_name = "core/pet_form.html"
    success_url = reverse_lazy("pet_list")

    def form_valid(self, form):
        messages.success(self.request, "Pet updated.")
        return super().form_valid(form)


class PetDeleteView(LoginRequiredMixin, DeleteView):
    model = Pet
    template_name = "core/pet_confirm_delete.html"
    success_url = reverse_lazy("pet_list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Pet deleted.")
        return super().delete(request, *args, **kwargs)


# -----------------------------
# Bookings tab (list & manage)
# -----------------------------
@login_required
def booking_list(request):
    from .models import Booking
    # parse filters
    range_label = request.GET.get("range", "this-week")
    start_q = request.GET.get("start")  # for custom
    end_q = request.GET.get("end")
    q = (request.GET.get("q") or "").strip()
    start_dt, end_dt = parse_label(range_label, start_param=start_q, end_param=end_q)
    qs = (
        Booking.objects.select_related("client")
        .filter(start_dt__gte=start_dt, start_dt__lt=end_dt)
        .exclude(status__in=["cancelled", "canceled", "void", "voided"])
        .exclude(deleted=True)
        .order_by("start_dt")
    )
    if q:
        qs = qs.filter(
            Q(client__name__icontains=q)
            | Q(service_label__icontains=q)
            | Q(service_name__icontains=q)
            | Q(location__icontains=q)
            | Q(notes__icontains=q)
        )
    # keep selected ids for .ics export
    selected_ids = request.GET.get("ids", "")
    ctx = {
        "bookings": qs,
        "range_label": range_label,
        "q": q,
        "start_q": start_q or start_dt.date().isoformat(),
        "end_q": end_q or end_dt.date().isoformat(),
        "presets": list_presets(),
        "selected_ids": selected_ids,
        "start_dt": start_dt,
        "end_dt": end_dt,
    }
    return render(request, "core/booking_list.html", ctx)


@login_required
def booking_open_invoice(request, booking_id: int):
    from .models import Booking
    b = get_object_or_404(Booking, id=booking_id)
    if not b.stripe_invoice_id:
        messages.warning(request, "This booking does not have an invoice.")
        params = urlencode({"range": request.GET.get("range", "this-week")})
        return HttpResponseRedirect(f"{reverse_lazy('booking_list')}?{params}")
    url = open_invoice_smart(b.stripe_invoice_id)
    return HttpResponseRedirect(url)


@login_required
def booking_soft_delete(request, booking_id: int):
    from .models import Booking
    b = get_object_or_404(Booking, id=booking_id)
    b.deleted = True
    b.save(update_fields=["deleted"])
    messages.success(request, "Booking deleted.")
    params = urlencode({"range": request.GET.get("range", "this-week")})
    return HttpResponseRedirect(f"{reverse_lazy('booking_list')}?{params}")


@login_required
def booking_export_ics(request: HttpRequest) -> HttpResponse:
    """
    Export ICS for either selected `ids` (comma-separated) or current filtered range.
    """
    from .models import Booking
    ids = (request.GET.get("ids") or "").strip()
    alarm = (request.GET.get("alarm") == "1")
    if ids:
        id_list = [int(x) for x in ids.split(",") if x.isdigit()]
        qs = Booking.objects.filter(id__in=id_list, deleted=False)
    else:
        range_label = request.GET.get("range", "this-week")
        start_q = request.GET.get("start")
        end_q = request.GET.get("end")
        start_dt, end_dt = parse_label(range_label, start_param=start_q, end_param=end_q)
        qs = (
            Booking.objects.filter(start_dt__gte=start_dt, start_dt__lt=end_dt, deleted=False)
            .exclude(status__in=["cancelled", "canceled", "void", "voided"])
            .order_by("start_dt")
        )
    ics = bookings_to_ics(qs, alarm=alarm)
    resp = HttpResponse(ics, content_type="text/calendar")
    resp["Content-Disposition"] = 'attachment; filename="bookings.ics"'
    return resp


# -----------------------------
# Subscriptions tab
# -----------------------------
@login_required
def subscriptions_list(request: HttpRequest) -> HttpResponse:
    """List distinct subscription IDs inferred from future active holds."""
    from .models import SubOccurrence
    now = timezone.now().astimezone(TZ)
    rows = (
        SubOccurrence.objects
        .filter(active=True, start_dt__gte=now)
        .values("stripe_subscription_id")
        .distinct()
    )
    subs = []
    for r in rows:
        sid = r["stripe_subscription_id"]
        next_occ = (
            SubOccurrence.objects
            .filter(stripe_subscription_id=sid, active=True, start_dt__gte=now)
            .order_by("start_dt")
            .first()
        )
        count = (
            SubOccurrence.objects
            .filter(stripe_subscription_id=sid, active=True, start_dt__gte=now)
            .count()
        )
        subs.append({
            "id": sid,
            "next_dt": next_occ.start_dt if next_occ else None,
            "upcoming": count,
        })
    return render(request, "core/subscriptions.html", {"subs": subs})


@login_required
def subscriptions_sync(request: HttpRequest) -> HttpResponse:
    """Run the unified sync and show a toast with stats."""
    stats = sync_subscriptions_to_bookings_and_calendar()
    messages.success(request, f"Sync complete — processed: {stats.get('processed')}, created: {stats.get('created')}, cleaned: {stats.get('cleaned')}, errors: {stats.get('errors')}")
    return redirect("subscriptions_list")


@login_required
def subscription_delete(request: HttpRequest, sub_id: str) -> HttpResponse:
    """
    Cancel subscription in Stripe and remove future holds.
    """
    from .models import SubOccurrence
    # Cancel in Stripe (no-op if key missing will raise; show friendly error)
    try:
        cancel_subscription_immediately(sub_id)
    except Exception as e:
        messages.error(request, f"Stripe cancel failed: {e}")
        return redirect("subscriptions_list")
    # Clean future holds
    now = timezone.now().astimezone(TZ)
    deleted, _ = SubOccurrence.objects.filter(
        stripe_subscription_id=sub_id, start_dt__gte=now
    ).delete()
    messages.success(request, f"Subscription {sub_id} cancelled. Removed {deleted} future holds.")
    return redirect("subscriptions_list")

# -----------------------------
# Admin Tasks (AdminEvent CRUD)
# -----------------------------
class AdminEventForm(ModelForm):
    class Meta:
        from .models import AdminEvent
        model = AdminEvent
        fields = ["due_dt", "title", "notes"]

@login_required
def admin_tasks_list(request: HttpRequest) -> HttpResponse:
    """List AdminEvent with Upcoming (default) / Past filters and a search box."""
    from .models import AdminEvent
    filt = (request.GET.get("f") or "upcoming").lower()
    q = (request.GET.get("q") or "").strip()
    now = timezone.now().astimezone(TZ)
    qs = AdminEvent.objects.all()
    if filt == "past":
        qs = qs.filter(due_dt__lt=now)
    else:
        filt = "upcoming"
        qs = qs.filter(due_dt__gte=now)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(notes__icontains=q))
    qs = qs.order_by("due_dt")
    return render(request, "core/admin_tasks_list.html", {"rows": qs, "f": filt, "q": q})

@login_required
@require_http_methods(["GET", "POST"])
def admin_task_create(request: HttpRequest) -> HttpResponse:
    from .models import AdminEvent
    form = AdminEventForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Task created.")
        return redirect("admin_tasks_list")
    return render(request, "core/admin_task_form.html", {"form": form, "obj": None})

@login_required
@require_http_methods(["GET", "POST"])
def admin_task_edit(request: HttpRequest, pk: int) -> HttpResponse:
    from .models import AdminEvent
    obj = get_object_or_404(AdminEvent, pk=pk)
    form = AdminEventForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Task updated.")
        return redirect("admin_tasks_list")
    return render(request, "core/admin_task_form.html", {"form": form, "obj": obj})

@login_required
@require_http_methods(["GET", "POST"])
def admin_task_delete(request: HttpRequest, pk: int) -> HttpResponse:
    from .models import AdminEvent
    obj = get_object_or_404(AdminEvent, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Task deleted.")
        return redirect("admin_tasks_list")
    return render(request, "core/admin_task_confirm_delete.html", {"obj": obj})


# -----------------------------
# CRM Tags
# -----------------------------
@login_required
def tags_list(request: HttpRequest) -> HttpResponse:
    q = (request.GET.get("q") or "").strip()
    qs = Tag.objects.all()
    if q:
        qs = qs.filter(name__icontains=q)
    qs = qs.order_by("name")
    return render(request, "core/tags_list.html", {"rows": qs, "q": q})


@login_required
@require_http_methods(["GET", "POST"])
def tag_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        color = (request.POST.get("color") or "").strip() or None
        if not name:
            messages.error(request, "Name is required.")
        else:
            Tag.objects.create(name=name, color=color)
            messages.success(request, "Tag created.")
            return redirect("tags_list")
    return render(request, "core/tag_form.html", {"obj": None})


@login_required
@require_http_methods(["GET", "POST"])
def tag_edit(request: HttpRequest, pk: int) -> HttpResponse:
    obj = get_object_or_404(Tag, pk=pk)
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        color = (request.POST.get("color") or "").strip() or None
        if not name:
            messages.error(request, "Name is required.")
        else:
            obj.name = name
            obj.color = color
            obj.save(update_fields=["name", "color"])
            messages.success(request, "Tag updated.")
            return redirect("tags_list")
    return render(request, "core/tag_form.html", {"obj": obj})


@login_required
@require_http_methods(["GET", "POST"])
def tag_delete(request: HttpRequest, pk: int) -> HttpResponse:
    obj = get_object_or_404(Tag, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Tag deleted.")
        return redirect("tags_list")
    return render(request, "core/tag_confirm_delete.html", {"obj": obj})


# -----------------------------
# API: service info → canonical + price
# -----------------------------
@login_required
def api_service_info(request: HttpRequest) -> JsonResponse:
    """
    Query params:
      - service_code (optional)
      - service_name (optional)
      - service_label (optional)
      - price_cents (optional override)
    Returns canonical fields incl. price_cents.
    """
    code  = request.GET.get("service_code") or None
    name  = request.GET.get("service_name") or None
    label = request.GET.get("service_label") or None
    price = request.GET.get("price_cents")
    try:
        price = int(price) if price not in (None, "",) else None
    except Exception:
        price = None
    info = get_canonical_service_info(
        service_code=code,
        service_name=name,
        service_label=label,
        price_cents=price,
    )
    return JsonResponse(info)


def stripe_status_view(request: HttpRequest) -> HttpResponse:
    """
    Show Stripe key status and a quick peek at the live catalog (count).
    Allow manual refresh via ?refresh=1
    """
    refresh = request.GET.get("refresh") == "1"
    try:
        services = list_booking_services(force_refresh=refresh)
        svc_count = len(services)
        if refresh:
            messages.success(request, f"Refreshed service catalog ({svc_count} price(s)).")
        elif svc_count == 0:
            messages.warning(request, "No active prices found. Check your Stripe key or create active Prices.")
    except Exception as e:
        services = []
        svc_count = 0
        messages.error(request, f"Stripe error: {e}")
    ctx = {
        "catalog_count": svc_count,
        "catalog_preview": services[:5],  # tiny peek
    }
    return render(request, "core/stripe_status.html", ctx)


# -----------------------------
# Client Portal
# -----------------------------
@login_required
def portal_home(request: HttpRequest) -> HttpResponse:
    """
    Client-facing home page.
    - If the logged-in user is linked to a Client, show upcoming bookings (next 90 days).
    - Otherwise, show a message explaining no client profile is linked.
    """
    from .models import Client, Booking
    user = request.user
    client = getattr(user, "client_profile", None)  # via Client.user OneToOne
    if not client:
        return render(request, "core/portal_home.html", {
            "client": None,
            "bookings": [],
            "note": "Your login is not linked to a client profile yet. Please contact support.",
        })
    now = timezone.now().astimezone(TZ)
    horizon = now + timezone.timedelta(days=90)
    rows = (
        Booking.objects.filter(
            client=client,
            start_dt__gte=now,
            start_dt__lt=horizon,
            deleted=False,
        )
        .exclude(status__in=["cancelled", "canceled", "void", "voided"])
        .order_by("start_dt")
    )
    return render(request, "core/portal_home.html", {
        "client": client,
        "bookings": rows,
        "note": "",
    })


# -----------------------------
# Portal Booking: create
# -----------------------------
@login_required
def portal_booking_create(request: HttpRequest) -> HttpResponse:
    """
    Client-facing booking form using live Stripe catalog.
    Validates availability against Bookings + SubOccurrence (active).
    On success: creates booking and applies credit-first + invoice reuse.
    Redirects to confirmation showing invoice URL if due.
    """
    from .models import Client, Booking, SubOccurrence
    user = request.user
    client = getattr(user, "client_profile", None)
    if not client:
        messages.error(request, "Your login is not linked to a client profile.")
        return redirect("portal_home")

    # Build service choices from live catalog
    catalog = list_booking_services(force_refresh=False)
    # value: price_id (preferred stable choice), but we still resolve via label/name if needed
    service_choices = [(s["price_id"], f'{s.get("display_name") or s.get("service_code") or "Service"} — ${(s.get("amount_cents") or 0)/100:.2f}') for s in catalog]

    if request.method == "POST":
        price_id = (request.POST.get("service_price_id") or "").strip()
        location = (request.POST.get("location") or "").strip()
        notes = (request.POST.get("notes") or "").strip()
        start_raw = (request.POST.get("start_dt") or "").strip()
        end_raw = (request.POST.get("end_dt") or "").strip()

        # Parse datetimes in Australia/Brisbane
        try:
            # Expect HTML5 datetime-local (YYYY-MM-DDTHH:MM)
            from datetime import datetime
            start_dt = datetime.fromisoformat(start_raw)
            end_dt = datetime.fromisoformat(end_raw)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=TZ)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=TZ)
        except Exception:
            messages.error(request, "Invalid start/end date/time.")
            return render(request, "core/portal_booking_form.html", {
                "service_choices": service_choices,
                "defaults": request.POST,
            })

        if end_dt <= start_dt:
            messages.error(request, "End time must be after start time.")
            return render(request, "core/portal_booking_form.html", {
                "service_choices": service_choices,
                "defaults": request.POST,
            })

        # Resolve catalog row by price_id; fall back to canonical resolver for label/name
        selected = next((s for s in catalog if s["price_id"] == price_id), None)
        if not selected:
            messages.error(request, "Please choose a valid service.")
            return render(request, "core/portal_booking_form.html", {
                "service_choices": service_choices,
                "defaults": request.POST,
            })

        # Availability: no overlap with any non-cancelled booking; also block if overlapping an active hold.
        overlap_q = Q(start_dt__lt=end_dt, end_dt__gt=start_dt)
        clashes = (
            Booking.objects
            .filter(overlap_q)
            .exclude(status__in=["cancelled", "canceled", "void", "voided"])
            .exclude(deleted=True)
            .exists()
        )
        hold_clashes = (
            SubOccurrence.objects
            .filter(active=True, start_dt__lt=end_dt, end_dt__gt=start_dt)
            .exists()
        )
        if clashes or hold_clashes:
            messages.error(request, "That time is not available. Please choose a different slot.")
            return render(request, "core/portal_booking_form.html", {
                "service_choices": service_choices,
                "defaults": request.POST,
            })

        # Build a single-row batch to reuse credit+invoice workflow
        row = {
            "start_dt": start_dt,
            "end_dt": end_dt,
            "service_label": selected.get("display_name"),
            "service_name": selected.get("display_name"),
            "service_code": selected.get("service_code"),
            "price_cents": selected.get("amount_cents"),
            "location": location,
            "dogs": 1,
            "notes": notes,
        }
        result = create_bookings_from_rows(client, [row])
        b = result["bookings"][0]  # the one we just created

        # Decide what to show: public invoice URL if any amount due (booking has stripe_invoice_id)
        hosted_url = None
        if b.stripe_invoice_id:
            hosted_url = get_invoice_public_url(b.stripe_invoice_id)

        # Stash confirmation data in session (simple pass-through) and redirect (avoid form resubmits)
        request.session["portal_confirm"] = {
            "booking_id": b.id,
            "service": b.service_label or b.service_name or b.service_code or "Service",
            "start": b.start_dt.isoformat(),
            "end": b.end_dt.isoformat(),
            "due": bool(b.stripe_invoice_id),
            "invoice_url": hosted_url,
        }
        return redirect("portal_booking_confirm")

    # GET: render form
    return render(request, "core/portal_booking_form.html", {
        "service_choices": service_choices,
        "defaults": {},
    })


@login_required
def portal_booking_confirm(request: HttpRequest) -> HttpResponse:
    ctx = request.session.pop("portal_confirm", None)
    if not ctx:
        messages.info(request, "No recent booking found.")
        return redirect("portal_home")
    return render(request, "core/portal_booking_confirm.html", {"ctx": ctx, "TZ": TZ})