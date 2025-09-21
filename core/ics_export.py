"""
ICS Export functionality for NewFarm Dog Walking App.

This module provides helpers to render bookings to valid iCalendar format.
"""

from icalendar import Calendar, Event
from django.utils import timezone
from datetime import datetime, timedelta
import pytz
from typing import List

from .models import Booking
from .domain_rules import is_overnight


def create_ical_calendar() -> Calendar:
    """
    Create a basic iCalendar calendar with proper headers.
    
    Returns:
        Calendar: Configured iCalendar Calendar object
    """
    cal = Calendar()
    cal.add('prodid', '-//NewFarm Dog Walking App//NewFarm Dog Walking App//EN')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    cal.add('x-wr-calname', 'NewFarm Dog Walking Bookings')
    cal.add('x-wr-caldesc', 'Dog walking and pet service bookings')
    return cal


def get_brisbane_timezone():
    """
    Get the Australia/Brisbane timezone object.
    
    Returns:
        pytz timezone object for Australia/Brisbane
    """
    return pytz.timezone('Australia/Brisbane')


def booking_to_vevent(booking: Booking) -> Event:
    """
    Convert a Booking model instance to an iCalendar Event.
    
    Args:
        booking: Booking model instance
        
    Returns:
        Event: iCalendar Event object representing the booking
    """
    event = Event()
    
    # Basic event details
    event.add('uid', f'booking-{booking.id}@newfarm-dog-walking.com')
    event.add('summary', f'{booking.service_name} - {booking.client.name}')
    
    # Description with details
    description_parts = [
        f'Client: {booking.client.name}',
        f'Service: {booking.service_name}',
        f'Dogs: {booking.dogs}',
        f'Location: {booking.location}' if booking.location else '',
    ]
    
    if booking.notes:
        description_parts.append(f'Notes: {booking.notes}')
    
    description = '\\n'.join(filter(None, description_parts))
    event.add('description', description)
    
    # Location
    if booking.location:
        event.add('location', booking.location)
    
    # Dates and times in Australia/Brisbane timezone
    brisbane_tz = get_brisbane_timezone()
    
    # Convert to Brisbane timezone
    start_dt = booking.start_dt.astimezone(brisbane_tz)
    end_dt = booking.end_dt.astimezone(brisbane_tz)
    
    # Handle overnight bookings - extend by +1 day
    if is_overnight(booking.service_label or booking.service_name):
        end_dt = end_dt + timedelta(days=1)
    
    event.add('dtstart', start_dt)
    event.add('dtend', end_dt)
    
    # Additional metadata
    event.add('status', 'CONFIRMED')
    event.add('transp', 'OPAQUE')  # Show as busy
    
    # Categories based on service
    if 'walk' in booking.service_name.lower():
        event.add('categories', 'Dog Walking')
    elif 'grooming' in booking.service_name.lower():
        event.add('categories', 'Grooming')
    elif 'sitting' in booking.service_name.lower():
        event.add('categories', 'Pet Sitting')
    else:
        event.add('categories', 'Pet Services')
    
    # Creation timestamp
    event.add('created', datetime.now(brisbane_tz))
    event.add('dtstamp', datetime.now(brisbane_tz))
    
    return event


def bookings_to_ics_string(bookings) -> str:
    """
    Convert a QuerySet of bookings to an iCalendar string.
    
    Args:
        bookings: QuerySet of Booking objects
        
    Returns:
        str: iCalendar formatted string
    """
    cal = create_ical_calendar()
    
    for booking in bookings:
        # Skip deleted, cancelled, or voided bookings
        if (booking.deleted or 
            'cancel' in booking.status.lower() or 
            'void' in booking.status.lower()):
            continue
            
        event = booking_to_vevent(booking)
        cal.add_component(event)
    
    return cal.to_ical().decode('utf-8')


def export_all_bookings() -> str:
    """
    Export all active bookings to iCalendar format.
    
    Returns:
        str: iCalendar formatted string containing all active bookings
    """
    bookings = Booking.objects.filter(
        deleted=False
    ).exclude(
        status__icontains='cancel'
    ).exclude(
        status__icontains='void'
    ).order_by('start_dt')
    
    return bookings_to_ics_string(bookings)


def export_bookings_by_ids(booking_ids: List[int]) -> str:
    """
    Export specific bookings by their IDs to iCalendar format.
    
    Args:
        booking_ids: List of booking IDs to export
        
    Returns:
        str: iCalendar formatted string containing specified bookings
    """
    bookings = Booking.objects.filter(
        id__in=booking_ids,
        deleted=False
    ).exclude(
        status__icontains='cancel'
    ).exclude(
        status__icontains='void'
    ).order_by('start_dt')
    
    return bookings_to_ics_string(bookings)