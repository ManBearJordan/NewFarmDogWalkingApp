"""
Admin views for Stripe key management.
"""
from django.contrib import admin
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib import messages
import json

from .stripe_key_manager import get_stripe_key, get_key_status, update_stripe_key


@staff_member_required
def stripe_status_view(request):
    """Admin view for Stripe key status and management."""
    if request.method == 'POST':
        # Handle form submission to update key
        new_key = request.POST.get('stripe_key', '').strip()
        if new_key:
            try:
                update_stripe_key(new_key)
                messages.success(request, 'Stripe key updated successfully.')
            except ValueError as e:
                messages.error(request, f'Error: {e}')
        else:
            messages.error(request, 'Please provide a valid Stripe key.')
        
        return HttpResponseRedirect('/admin/stripe/')
    
    # GET request - show status and form
    status = get_key_status()
    key = get_stripe_key()
    
    # Mask the key for display (show only first and last few characters)
    masked_key = None
    if key:
        if len(key) > 12:
            masked_key = key[:8] + '...' + key[-4:]
        else:
            masked_key = key[:4] + '...'
    
    context = {
        'status': status,
        'masked_key': masked_key,
        'title': 'Stripe Configuration',
    }
    
    return render(request, 'admin/stripe_status.html', context)


@staff_member_required
@csrf_exempt
def stripe_diagnostics_view(request):
    """JSON endpoint for Stripe status diagnostics."""
    status = get_key_status()
    key = get_stripe_key()
    
    # Add more diagnostic information
    diagnostics = {
        'configured': status['configured'],
        'mode': status['mode'],
        'key_present': bool(key),
        'key_length': len(key) if key else 0,
        'key_format_valid': False
    }
    
    if key:
        # Basic validation of key format
        if key.startswith(('sk_test_', 'sk_live_')) and len(key) > 20:
            diagnostics['key_format_valid'] = True
    
    return JsonResponse(diagnostics)