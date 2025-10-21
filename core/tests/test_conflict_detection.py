"""
Tests for the new conflict detection utility.
"""
import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from zoneinfo import ZoneInfo
from datetime import timedelta
from core.models import Client, Booking, Service
from core.utils_conflicts import has_conflict

TZ = ZoneInfo("Australia/Brisbane")


@pytest.mark.django_db
def test_has_conflict_detects_overlapping_bookings():
    """Test that has_conflict correctly detects overlapping bookings."""
    # Create client
    client = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="123",
        address="Test",
        status="active"
    )
    
    # Create existing booking from 10:00 to 11:00
    start1 = timezone.datetime(2025, 9, 24, 10, 0, tzinfo=TZ)
    end1 = timezone.datetime(2025, 9, 24, 11, 0, tzinfo=TZ)
    booking1 = Booking.objects.create(
        client=client,
        service_code="walk",
        service_name="Walk",
        service_label="Walk",
        start_dt=start1,
        end_dt=end1,
        status="confirmed",
        location="Park"
    )
    
    # Test: New booking from 10:30 to 11:30 should conflict
    start2 = timezone.datetime(2025, 9, 24, 10, 30, tzinfo=TZ)
    end2 = timezone.datetime(2025, 9, 24, 11, 30, tzinfo=TZ)
    assert has_conflict(client, start2, end2) is True
    
    # Test: New booking from 11:00 to 12:00 should NOT conflict (end=start is OK)
    start3 = timezone.datetime(2025, 9, 24, 11, 0, tzinfo=TZ)
    end3 = timezone.datetime(2025, 9, 24, 12, 0, tzinfo=TZ)
    assert has_conflict(client, start3, end3) is False
    
    # Test: New booking from 9:00 to 10:00 should NOT conflict
    start4 = timezone.datetime(2025, 9, 24, 9, 0, tzinfo=TZ)
    end4 = timezone.datetime(2025, 9, 24, 10, 0, tzinfo=TZ)
    assert has_conflict(client, start4, end4) is False


@pytest.mark.django_db
def test_has_conflict_excludes_specified_booking():
    """Test that has_conflict can exclude a specific booking ID."""
    client = Client.objects.create(
        name="Test Client",
        email="test2@example.com",
        phone="123",
        address="Test",
        status="active"
    )
    
    # Create booking
    start = timezone.datetime(2025, 9, 24, 10, 0, tzinfo=TZ)
    end = timezone.datetime(2025, 9, 24, 11, 0, tzinfo=TZ)
    booking = Booking.objects.create(
        client=client,
        service_code="walk",
        service_name="Walk",
        service_label="Walk",
        start_dt=start,
        end_dt=end,
        status="confirmed",
        location="Park"
    )
    
    # Same time should conflict normally
    assert has_conflict(client, start, end) is True
    
    # But if we exclude this booking, no conflict
    assert has_conflict(client, start, end, exclude_booking_id=booking.id) is False


@pytest.mark.django_db
def test_portal_booking_form_prevents_conflicts():
    """Test that PortalBookingForm uses conflict detection."""
    from core.forms import PortalBookingForm
    from datetime import date, time
    
    # Create client and service
    client = Client.objects.create(
        name="Test Client",
        email="form@example.com",
        phone="123",
        address="Test",
        status="active"
    )
    service = Service.objects.create(
        code="walk30",
        name="30min Walk",
        duration_minutes=30,
        is_active=True
    )
    
    # Create existing booking at 10:00-10:30
    start = timezone.datetime(2025, 9, 24, 10, 0, tzinfo=TZ)
    end = timezone.datetime(2025, 9, 24, 10, 30, tzinfo=TZ)
    Booking.objects.create(
        client=client,
        service=service,
        service_code="walk30",
        service_name="30min Walk",
        service_label="30min Walk",
        start_dt=start,
        end_dt=end,
        status="confirmed",
        location="Park"
    )
    
    # Try to book overlapping time 10:15-10:45
    form_data = {
        "service": service.id,
        "date": date(2025, 9, 24),
        "time": time(10, 15),
        "location": "Home"
    }
    form = PortalBookingForm(data=form_data, client=client)
    
    # Form should be invalid due to conflict
    assert form.is_valid() is False
    assert "conflicts" in str(form.errors).lower()
    
    # Try booking non-overlapping time 11:00-11:30
    form_data2 = {
        "service": service.id,
        "date": date(2025, 9, 24),
        "time": time(11, 0),
        "location": "Home"
    }
    form2 = PortalBookingForm(data=form_data2, client=client)
    
    # Form should be valid (no conflict)
    assert form2.is_valid() is True
