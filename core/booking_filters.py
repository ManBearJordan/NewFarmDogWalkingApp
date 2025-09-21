"""
Booking filtering utilities for consistent status filtering across views.

Provides reusable functions to filter bookings by status, excluding
deleted, cancelled, and voided bookings from listings.
"""

from django.db.models import QuerySet
from .models import Booking


def filter_active_bookings(queryset: QuerySet) -> QuerySet:
    """
    Filter booking queryset to exclude deleted, cancelled, and voided bookings.
    
    Args:
        queryset: Base queryset of Booking objects
        
    Returns:
        QuerySet: Filtered queryset excluding inactive bookings
    """
    return queryset.filter(
        deleted=False
    ).exclude(
        status__icontains='cancel'
    ).exclude(
        status__icontains='void'
    )


def get_active_bookings():
    """
    Get all active bookings (excludes deleted, cancelled, voided).
    
    Returns:
        QuerySet: All active bookings
    """
    return filter_active_bookings(Booking.objects.all())