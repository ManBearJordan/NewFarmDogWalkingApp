from datetime import datetime
from django.db.models import Q
from .models import Booking


def has_conflict(client, start_dt, end_dt, exclude_booking_id=None):
    """
    Returns True if there is any booking overlapping [start_dt, end_dt) for this client.
    Overlap rule: (A.start < B.end) and (A.end > B.start)
    """
    qs = Booking.objects.filter(client=client)
    if exclude_booking_id:
        qs = qs.exclude(id=exclude_booking_id)
    return qs.filter(
        Q(start_dt__lt=end_dt) & Q(end_dt__gt=start_dt)
    ).exists()
