"""
Booking creation service with billing integration.

This module provides functionality to create multiple bookings with
credit application and Stripe invoice management.
"""

from datetime import timedelta
from typing import Dict, List, Optional
from django.db import transaction

from .models import Client, Booking
from .credit import get_client_credit, deduct_client_credit
from .service_map import resolve_service_fields
from .domain_rules import is_overnight
from .stripe_integration import (
    ensure_customer,
    create_or_reuse_draft_invoice,
    push_invoice_items_from_booking,
)
from .unified_booking_helpers import create_booking_with_unified_fields, get_canonical_service_info


def create_bookings_from_rows(client, rows):
    """
    rows: list of dicts from the batch UI. Each row minimally contains:
      start_dt, end_dt, service_code/name/label (any of them), price_cents (optional),
      location, dogs, notes.
    """
    if not rows:
        return {
            "bookings": [],
            "total_credit_used": 0,
            "invoice_id": None,
        }

    total_credit_available = get_client_credit(client) 
    total_credit_used = 0
    bookings_to_invoice = []
    created_bookings = []
    invoice_id = None

    with transaction.atomic():
        for row in rows:
            # Canonicalise inputs and create the booking using the unified helper
            booking = create_booking_with_unified_fields(
                client=client,
                start_dt=row["start_dt"],
                end_dt=row["end_dt"],
                location=row.get("location") or "",
                dogs=row.get("dogs") or 1,
                notes=row.get("notes") or "",
                status="confirmed",
                price_cents=row.get("price_cents"),
                service_code=row.get("service_code"),
                service_name=row.get("service_name"),
                service_label=row.get("service_label"),
            )

            price_due = booking.price_cents or 0
            # Apply credit per row
            credit_for_row = min(price_due, max(0, total_credit_available - total_credit_used))
            net_due = price_due - credit_for_row
            total_credit_used += credit_for_row

            # If there's still amount due after credit, add to invoice
            if net_due > 0:
                # Ensure we have a customer and invoice
                customer_id = ensure_customer(client)
                if invoice_id is None:
                    invoice_id = create_or_reuse_draft_invoice(client)
                
                # Update booking with invoice ID
                booking.stripe_invoice_id = invoice_id
                booking.save()
                bookings_to_invoice.append(booking)
            
            created_bookings.append(booking)

        # Push invoice items for bookings that need invoicing
        for booking in bookings_to_invoice:
            push_invoice_items_from_booking(booking, invoice_id)

        # Deduct the total credit used
        if total_credit_used > 0:
            deduct_client_credit(client, total_credit_used)

    return {
        "bookings": created_bookings,
        "total_credit_used": total_credit_used,
        "invoice_id": invoice_id,
    }


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
    
    created_bookings: List[Booking] = []
    bookings_to_invoice: List[Booking] = []
    total_credit_used = 0
    invoice_id: Optional[str] = None

    # Get current client credit once, allocate per row, deduct once at end
    remaining_credit = get_client_credit(client)

    with transaction.atomic():
        # Process each booking row
        for row in rows:
            # Accept either service_label or service_code from input
            service_label_or_code = row.get('service_label') or row.get('service_code', '')
            if not service_label_or_code:
                # Skip rows without a service identifier
                continue

            # Resolve canonical service_code and display label
            service_code, display_label = resolve_service_fields(service_label_or_code)

            # Prepare booking dates
            start_dt = row['start_dt']
            end_dt = row['end_dt']

            # If overnight service, increment end_dt by +1 day
            if is_overnight(service_label_or_code) or is_overnight(service_code):
                end_dt = end_dt + timedelta(days=1)

            # Price (default to 0 if missing to be defensive)
            price_cents = row.get('price_cents', 0)

            # Apply available credit to this booking
            credit_to_use = min(remaining_credit, price_cents)
            amount_due = price_cents - credit_to_use

            # Update running totals
            total_credit_used += credit_to_use
            remaining_credit -= credit_to_use

            # Determine invoice id for this booking (if any)
            booking_invoice_id = None
            if amount_due > 0:
                if invoice_id is None:
                    # Create/reuse ONE draft invoice for the whole batch
                    invoice_id = create_or_reuse_draft_invoice(client)
                booking_invoice_id = invoice_id

            # Create the booking record
            booking = Booking.objects.create(
                client=client,
                service_code=service_code,
                service_name=display_label,
                service_label=service_label_or_code,
                start_dt=start_dt,
                end_dt=end_dt,
                location=row.get('location', ''),
                dogs=row.get('dogs', 1),
                status='confirmed',  # default
                price_cents=price_cents,
                notes=row.get('notes', ''),
                stripe_invoice_id=booking_invoice_id,
                deleted=False,
            )
            created_bookings.append(booking)

            # Track bookings that need invoice items
            if amount_due > 0:
                bookings_to_invoice.append(booking)

        # Push invoice items (once per booking) to the single draft invoice
        if bookings_to_invoice and invoice_id:
            for booking in bookings_to_invoice:
                push_invoice_items_from_booking(booking, invoice_id)

        # Commit the credit deduction once after the loop (atomic & validated)
        if total_credit_used > 0:
            deduct_client_credit(client, total_credit_used)

    return {
        'created_ids': [b.id for b in created_bookings],
        'invoice_id': invoice_id,
        'total_credit_used': total_credit_used,
    }