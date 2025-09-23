from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional, Dict, Any

from django.utils import timezone

from .service_map import resolve_service_fields
from .stripe_integration import list_booking_services


def _lookup_price_cents(service_code: Optional[str]) -> Optional[int]:
    """Find default price in cents from the Stripe service catalog shim."""
    if not service_code:
        return None
    for s in list_booking_services():
        if s.get("service_code") == service_code:
            return int(s.get("amount_cents") or 0)
    return None


def get_canonical_service_info(
    *,
    service_code: Optional[str] = None,
    service_name: Optional[str] = None,
    service_label: Optional[str] = None,
    price_cents: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Resolve fuzzy inputs into canonical fields:
      - service_code, service_name, service_label
      - price_cents (from input or catalog default)
    Uses the existing resolve_service_fields() behaviour.
    """
    # Determine which input to use for resolution
    input_value = service_label or service_name or service_code or ""
    
    if input_value:
        # Use existing resolve_service_fields which takes single input
        code, name = resolve_service_fields(input_value)
        # If we had a specific service_label input, preserve it
        label = service_label if service_label else input_value
    else:
        code, name, label = "", "", ""
    
    amount = price_cents if price_cents is not None else _lookup_price_cents(code)
    return {
        "service_code": code,
        "service_name": name,
        "service_label": label,
        "price_cents": amount,
    }


def create_booking_with_unified_fields(
    *,
    client,
    start_dt,
    end_dt,
    location: str = "",
    dogs: int = 1,
    notes: str = "",
    status: str = "confirmed",
    price_cents: Optional[int] = None,
    service_code: Optional[str] = None,
    service_name: Optional[str] = None,
    service_label: Optional[str] = None,
):
    """
    Create & persist a Booking with canonicalised service fields.
    Also enforces the 'overnight' rule: if label implies overnight,
    ensure end_dt >= start_dt + 1 day.
    """
    from .models import Booking  # local import to avoid circulars

    info = get_canonical_service_info(
        service_code=service_code,
        service_name=service_name,
        service_label=service_label,
        price_cents=price_cents,
    )

    # Overnight rule (label-based)
    label_lower = (info["service_label"] or info["service_name"] or info["service_code"] or "").lower()
    if "overnight" in label_lower:
        if end_dt <= start_dt:
            end_dt = start_dt + timedelta(days=1)

    b = Booking.objects.create(
        client=client,
        start_dt=start_dt,
        end_dt=end_dt,
        location=location or "",
        dogs=dogs or 1,
        status=status,
        notes=notes or "",
        price_cents=info["price_cents"],
        service_code=info["service_code"],
        service_name=info["service_name"],
        service_label=info["service_label"],
    )
    return b