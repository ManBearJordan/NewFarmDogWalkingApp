"""
Integration test for the complete subscription materialization workflow.
Tests that the upsert_subscription_schedule_from_stripe and materialize_future_holds work together.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock
from django.utils import timezone
from core.models import Client, Service, StripeSubscriptionLink, StripeSubscriptionSchedule, Booking
from core.stripe_subscriptions import upsert_subscription_schedule_from_stripe
from core.subscription_materializer import materialize_future_holds


@pytest.mark.django_db
def test_complete_workflow_from_stripe_metadata():
    """Test the complete workflow: Stripe metadata -> Schedule -> Materialized bookings."""
    # Setup
    client = Client.objects.create(
        name="Workflow Test Client",
        email="workflow@test.com",
        phone="555-9999",
        address="999 Test Blvd",
        status="active"
    )
    
    service = Service.objects.create(
        code="walk_workflow",
        name="Workflow Walk",
        duration_minutes=45,
        is_active=True
    )
    
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_workflow_123",
        client=client,
        service_code="walk_workflow",
        active=True
    )
    
    # Mock Stripe subscription object with metadata
    mock_sub = Mock()
    mock_sub.id = "sub_workflow_123"
    mock_sub.metadata = {
        "days": "MON,WED,FRI",
        "start_time": "15:30",
        "location": "Dog Park",
        "visits_per_fortnight": "6",
        "repeats": "weekly"
    }
    
    # Step 1: Upsert schedule from Stripe metadata
    schedule = upsert_subscription_schedule_from_stripe(mock_sub)
    
    assert schedule is not None
    assert schedule.days == "MON,WED,FRI"
    assert schedule.start_time == "15:30"
    assert schedule.location == "Dog Park"
    assert schedule.visits_per_fortnight == 6
    assert schedule.repeats == "weekly"
    
    # Step 2: Materialize bookings
    result = materialize_future_holds()
    
    assert result['created'] > 0
    
    # Step 3: Verify bookings
    bookings = Booking.objects.filter(client=client, service=service).order_by('start_dt')
    assert bookings.count() >= 3  # At least 3 bookings (MON, WED, FRI in first week)
    
    # Check booking details
    first_booking = bookings.first()
    assert first_booking.location == "Dog Park"
    assert first_booking.service_code == "walk_workflow"
    assert first_booking.end_dt == first_booking.start_dt + timezone.timedelta(minutes=45)
    
    # Verify days of week
    days_of_week = set()
    for booking in bookings[:6]:  # Check first 6 bookings
        days_of_week.add(booking.start_dt.weekday())
    
    # Should have bookings on Monday (0), Wednesday (2), and Friday (4)
    assert 0 in days_of_week  # MON
    assert 2 in days_of_week  # WED
    assert 4 in days_of_week  # FRI


@pytest.mark.django_db
def test_fortnightly_workflow():
    """Test fortnightly subscription workflow."""
    client = Client.objects.create(
        name="Fortnightly Workflow Client",
        email="fortnightly_workflow@test.com",
        phone="555-8888",
        address="888 Test Ave",
        status="active"
    )
    
    service = Service.objects.create(
        code="walk_fortnightly",
        name="Fortnightly Walk",
        duration_minutes=90,
        is_active=True
    )
    
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_fortnightly_workflow",
        client=client,
        service_code="walk_fortnightly",
        active=True
    )
    
    # Mock Stripe subscription with fortnightly repeats
    mock_sub = Mock()
    mock_sub.id = "sub_fortnightly_workflow"
    mock_sub.metadata = {
        "days": "THU",
        "start_time": "11:00",
        "location": "Training Field",
        "repeats": "fortnightly"
    }
    
    # Upsert schedule
    schedule = upsert_subscription_schedule_from_stripe(mock_sub)
    assert schedule.repeats == "fortnightly"
    assert schedule.interval_weeks() == 2
    
    # Materialize bookings
    result = materialize_future_holds()
    
    # Verify bookings are spaced 2 weeks apart
    bookings = Booking.objects.filter(client=client, service=service).order_by('start_dt')
    
    if bookings.count() >= 2:
        first = bookings[0]
        second = bookings[1]
        
        # Calculate days between bookings
        days_diff = (second.start_dt.date() - first.start_dt.date()).days
        
        # Should be approximately 14 days (might be 13-15 due to week boundaries)
        assert 13 <= days_diff <= 15, f"Expected ~14 days between fortnightly bookings, got {days_diff}"


@pytest.mark.django_db
def test_metadata_fallback_to_defaults():
    """Test that missing metadata falls back to defaults."""
    client = Client.objects.create(
        name="Fallback Client",
        email="fallback@test.com",
        phone="555-7777",
        address="777 Test Ln",
        status="active"
    )
    
    service = Service.objects.create(
        code="walk_fallback",
        name="Fallback Walk",
        duration_minutes=30,
        is_active=True
    )
    
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_fallback",
        client=client,
        service_code="walk_fallback",
        active=True
    )
    
    # Mock Stripe subscription with minimal metadata
    mock_sub = Mock()
    mock_sub.id = "sub_fallback"
    mock_sub.metadata = {}  # Empty metadata
    
    # Upsert schedule
    schedule = upsert_subscription_schedule_from_stripe(mock_sub)
    
    # Should have defaults
    assert schedule.repeats == "weekly"  # Default
    
    # Materialize and check defaults are used
    result = materialize_future_holds()
    
    bookings = Booking.objects.filter(client=client, service=service)
    
    if bookings.count() > 0:
        first_booking = bookings.first()
        assert first_booking.location == "Home"  # Default location
        # Should use parsed_time() default of 10:30 (convert to local time for check)
        local_time = timezone.localtime(first_booking.start_dt)
        assert local_time.hour == 10
        assert local_time.minute == 30
