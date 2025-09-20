"""
Booking creation service with billing integration.

This module provides functionality to create multiple bookings with
credit application and Stripe invoice management.
"""

from datetime import timedelta
from typing import Dict, List, Optional
from django.db import transaction

from .models import Client, Booking
from .credit import get_client_credit, use_client_credit
from .service_map import resolve_service_fields
from .domain_rules import is_overnight
from .stripe_integration import create_or_reuse_draft_invoice, push_invoice_items_from_booking


def create_bookings_with_billing(client: Client, rows: List[Dict]) -> Dict:
    """
    Create multiple bookings with credit application and billing.
    
    Args:
        client: Client model instance
        rows: List of booking data dicts with keys:
              {service_label|service_code, start_dt, end_dt, location, dogs, price_cents, notes}
    
    Returns:
        Dict with keys: {created_ids: [int], invoice_id: str|None, total_credit_used: int}
    
    Behavior:
        - Resolve service_code + display_label via service_map.resolve_service_fields
        - If overnight, increment end_dt by +1 day
        - Apply client credit per row first
        - Reuse ONE draft invoice across all rows with non-zero due
        - Link booking.stripe_invoice_id when invoiced; leave NULL if fully credit-covered
        - Deduct credit once after loop
    """
    if not rows:
        return {
            'created_ids': [],
            'invoice_id': None,
            'total_credit_used': 0
        }
    
    created_bookings = []
    bookings_to_invoice = []
    total_credit_used = 0
    invoice_id = None
    
    # Get current client credit
    available_credit = get_client_credit(client)
    remaining_credit = available_credit
    
    with transaction.atomic():
        # Process each booking row
        for row in rows:
            # Resolve service fields
            service_label_or_code = row.get('service_label') or row.get('service_code', '')
            service_code, display_label = resolve_service_fields(service_label_or_code)
            
            # Prepare booking data
            start_dt = row['start_dt']
            end_dt = row['end_dt']
            
            # If overnight service, increment end_dt by +1 day
            if is_overnight(service_label_or_code) or is_overnight(service_code):
                end_dt = end_dt + timedelta(days=1)
            
            price_cents = row['price_cents']
            
            # Apply available credit to this booking
            credit_to_use = min(remaining_credit, price_cents)
            amount_due = price_cents - credit_to_use
            
            # Update running totals
            total_credit_used += credit_to_use
            remaining_credit -= credit_to_use
            
            # Determine stripe_invoice_id for this booking
            booking_invoice_id = None
            if amount_due > 0:
                # This booking will need to be invoiced
                if invoice_id is None:
                    # Create draft invoice for the batch (reuse if exists)
                    invoice_id = create_or_reuse_draft_invoice(client)
                booking_invoice_id = invoice_id
            
            # Create the booking
            booking = Booking.objects.create(
                client=client,
                service_code=service_code,
                service_name=display_label,
                service_label=service_label_or_code,
                start_dt=start_dt,
                end_dt=end_dt,
                location=row.get('location', ''),
                dogs=row.get('dogs', 1),
                status='confirmed',  # Default status
                price_cents=price_cents,
                notes=row.get('notes', ''),
                stripe_invoice_id=booking_invoice_id,
                deleted=False
            )
            
            created_bookings.append(booking)
            
            # Track bookings that need invoice items
            if amount_due > 0:
                bookings_to_invoice.append(booking)
        
        # Add invoice items for bookings that need billing
        if bookings_to_invoice and invoice_id:
            for booking in bookings_to_invoice:
                push_invoice_items_from_booking(booking, invoice_id)
        
        # Deduct total credit used from client (once at the end)
        if total_credit_used > 0:
            use_client_credit(client, total_credit_used)
    
    return {
        'created_ids': [booking.id for booking in created_bookings],
        'invoice_id': invoice_id,
        'total_credit_used': total_credit_used
    }