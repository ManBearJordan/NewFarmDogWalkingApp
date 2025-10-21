"""
Thin wrapper that tries to call your existing Stripe helpers (if present)
to create/link an invoice for a booking and return a hosted URL.
If none are available, returns None (sync/webhook will link later).
"""
from typing import Optional


def try_create_invoice_for_booking(booking) -> Optional[str]:
    """
    Try to create and link an invoice for the booking.
    Returns the invoice URL if successful, None otherwise.
    """
    # Strategy 1: booking_create_service.create_booking_invoice(booking) -> url
    try:
        from .booking_create_service import create_booking_invoice  # type: ignore
        url = create_booking_invoice(booking)
        return url
    except Exception:
        pass
    
    # Strategy 2: stripe_integration.create_or_update_invoice_for_booking(booking) -> url
    try:
        from .stripe_integration import create_or_update_invoice_for_booking  # type: ignore
        url = create_or_update_invoice_for_booking(booking)
        return url
    except Exception:
        pass
    
    # Strategy 3: stripe_integration.create_invoice_for_booking(booking) -> url
    try:
        from .stripe_integration import create_invoice_for_booking  # type: ignore
        url = create_invoice_for_booking(booking)
        return url
    except Exception:
        pass
    
    return None
