"""
Web views for the NewFarm Dog Walking App.

Provides simple views for client management and booking creation.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, date
from calendar import Calendar, monthrange
import json

from .models import Client, Booking, AdminEvent, SubOccurrence
from .booking_create_service import create_bookings_with_billing
from .stripe_integration import list_booking_services, open_invoice_smart
from .credit import use_client_credit


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
    # Add credit_aud field for template use
    for client in clients:
        client.credit_aud = client.credit_cents / 100.0
    
    return render(request, 'core/client_list.html', {
        'clients': clients
    })


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
            
            # Convert cents to AUD for display
            total_credit_used_aud = result['total_credit_used'] / 100.0
            client.credit_aud = client.credit_cents / 100.0
            
            created_bookings = Booking.objects.filter(id__in=result.get('created_ids', [])).order_by('start_dt')
            # Add price_aud field for template use
            for booking in created_bookings:
                booking.price_aud = booking.price_cents / 100.0
            
            return render(request, 'core/booking_batch_result.html', {
                'result': result,
                'client': client,
                'invoice_url': invoice_url,
                'total_credit_used_aud': total_credit_used_aud,
                'created_bookings': created_bookings
            })
            
        except Exception as e:
            messages.error(request, f'Error creating bookings: {e}')
            return redirect('booking_create_batch')
    
    # GET request - show form
    clients = Client.objects.filter(status='active').order_by('name')
    # Add credit_aud field for template use
    for client in clients:
        client.credit_aud = client.credit_cents / 100.0
    
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
    bookings = Booking.objects.filter(
        start_dt__date__gte=month_start,
        start_dt__date__lt=month_end,
        deleted=False
    ).exclude(
        status__icontains='cancel'
    ).exclude(
        status__icontains='void'
    )
    
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
            selected_bookings = Booking.objects.filter(
                start_dt__date=selected_dt,
                deleted=False
            ).exclude(
                status__icontains='cancel'
            ).exclude(
                status__icontains='void'
            ).order_by('start_dt')
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