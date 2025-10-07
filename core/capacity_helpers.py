"""
Capacity helpers for flexible timetable blocks.
"""
from django.utils import timezone
from django.db.models import Q
from .models import TimetableBlock, BlockCapacity, Booking, CapacityHold, ServiceDefaults
from datetime import datetime, timedelta

HOLD_MINUTES = 10


def get_default_duration_minutes(service_code: str) -> int:
    """Get default duration for a service code."""
    try:
        return ServiceDefaults.objects.get(service_code=service_code).duration_minutes
    except ServiceDefaults.DoesNotExist:
        return 60


def list_blocks_for_date(date):
    """List all timetable blocks for a given date."""
    return TimetableBlock.objects.filter(date=date).order_by("start_time")


def block_remaining_capacity(block: TimetableBlock, service_code: str) -> int:
    """
    Calculate remaining capacity for a service in a block.
    Counts active bookings and holds against the block capacity.
    """
    cap = BlockCapacity.objects.filter(block=block, service_code=service_code).first()
    if not cap:
        return 0
    
    # Count bookings in this block window for that service
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(block.date, block.start_time), tz)
    end_dt = timezone.make_aware(datetime.combine(block.date, block.end_time), tz)
    
    bookings_count = Booking.objects.filter(
        service_code=service_code,
        start_dt__lt=end_dt,
        end_dt__gt=start_dt,
        deleted=False
    ).exclude(status__in=["cancelled", "canceled", "void", "voided"]).count()
    
    # Count active holds (not expired)
    CapacityHold.purge_expired()
    holds_count = CapacityHold.objects.filter(
        block=block,
        service_code=service_code,
        expires_at__gt=timezone.now()
    ).count()
    
    remaining = max(cap.capacity - bookings_count - holds_count, 0)
    return remaining


def create_hold(block: TimetableBlock, service_code: str, client, minutes: int = HOLD_MINUTES):
    """Create a short-lived capacity hold."""
    expires = timezone.now() + timedelta(minutes=minutes)
    return CapacityHold.objects.create(
        block=block,
        service_code=service_code,
        client=client,
        expires_at=expires
    )
