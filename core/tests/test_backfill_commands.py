"""Tests for backfill and diagnostic management commands."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from io import StringIO
from django.core.management import call_command
from django.utils import timezone

from core.models import (
    Client, Booking, Service, StripeSubscriptionSchedule, 
    StripeSubscriptionLink, StripePriceMap
)


@pytest.mark.django_db
def test_occurs_on_datetime_weekly_schedule():
    """Test occurs_on_datetime method for weekly schedules"""
    # Create client and link
    client = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_test123",
        client=client,
        service_code="walk30",
        active=True
    )
    
    # Create a complete weekly schedule for Monday at 10:00
    schedule = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="mon",
        default_time="10:00",
        days="MON",
        start_time="10:00",
        location="Test Location",
        repeats=StripeSubscriptionSchedule.REPEATS_WEEKLY
    )
    
    # Test datetime that matches: Monday at 10:00
    monday_10am = datetime(2025, 1, 6, 10, 0)  # A Monday
    assert monday_10am.weekday() == 0  # Verify it's Monday
    assert schedule.occurs_on_datetime(monday_10am) is True
    
    # Test datetime that doesn't match: Tuesday at 10:00
    tuesday_10am = datetime(2025, 1, 7, 10, 0)  # A Tuesday
    assert schedule.occurs_on_datetime(tuesday_10am) is False
    
    # Test datetime that doesn't match: Monday at 11:00
    monday_11am = datetime(2025, 1, 6, 11, 0)  # Monday but wrong time
    assert schedule.occurs_on_datetime(monday_11am) is False


@pytest.mark.django_db
def test_occurs_on_datetime_fortnightly_returns_false():
    """Test occurs_on_datetime returns False for fortnightly schedules (ambiguous)"""
    client = Client.objects.create(
        name="Test Client",
        email="test2@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_test456",
        client=client,
        service_code="walk30",
        active=True
    )
    
    schedule = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="mon",
        default_time="10:00",
        days="MON",
        start_time="10:00",
        location="Test Location",
        repeats=StripeSubscriptionSchedule.REPEATS_FORTNIGHTLY
    )
    
    # Even though it matches the weekday and time, fortnightly is ambiguous
    monday_10am = datetime(2025, 1, 6, 10, 0)
    assert schedule.occurs_on_datetime(monday_10am) is False


@pytest.mark.django_db
def test_occurs_on_datetime_incomplete_schedule():
    """Test occurs_on_datetime returns False for incomplete schedules"""
    client = Client.objects.create(
        name="Test Client",
        email="test3@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_test789",
        client=client,
        service_code="walk30",
        active=True
    )
    
    # Create incomplete schedule (missing location)
    schedule = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="mon",
        default_time="10:00",
        days="MON",
        start_time="10:00",
        repeats=StripeSubscriptionSchedule.REPEATS_WEEKLY
        # Missing location - incomplete
    )
    
    monday_10am = datetime(2025, 1, 6, 10, 0)
    assert schedule.occurs_on_datetime(monday_10am) is False


@pytest.mark.django_db
def test_backfill_booking_end_times_dry_run():
    """Test backfill_booking_end_times command in dry-run mode"""
    # Create test data
    client = Client.objects.create(
        name="Test Client",
        email="backfill1@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    service = Service.objects.create(
        code="walk30",
        name="30 Min Walk",
        duration_minutes=30,
        is_active=True
    )
    
    start_time = timezone.now()
    booking = Booking.objects.create(
        client=client,
        service=service,
        service_code=service.code,
        service_name=service.name,
        service_label="Test Walk",
        start_dt=start_time,
        end_dt=start_time + timedelta(minutes=60),  # Wrong duration (60 instead of 30)
        location="Test Park",
        status="confirmed"
    )
    
    out = StringIO()
    call_command('backfill_booking_end_times', '--dry-run', stdout=out)
    output = out.getvalue()
    
    # Should report that it would fix the booking
    assert "Scanned=1" in output
    assert "Fixed end_dt=1" in output
    assert "DryRun=True" in output
    
    # Verify booking was NOT modified
    booking.refresh_from_db()
    assert booking.end_dt == start_time + timedelta(minutes=60)


@pytest.mark.django_db
def test_backfill_booking_end_times_actual_fix():
    """Test backfill_booking_end_times command actually fixes bookings"""
    client = Client.objects.create(
        name="Test Client",
        email="backfill2@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    service = Service.objects.create(
        code="walk60",
        name="60 Min Walk",
        duration_minutes=60,
        is_active=True
    )
    
    start_time = timezone.now()
    # Create with wrong duration initially
    wrong_end = start_time + timedelta(minutes=30)
    booking = Booking.objects.create(
        client=client,
        service=service,
        service_code=service.code,
        service_name=service.name,
        service_label="Test Walk",
        start_dt=start_time,
        end_dt=wrong_end,  # Wrong end time (30 mins instead of 60)
        location="Test Park",
        status="confirmed"
    )
    
    out = StringIO()
    call_command('backfill_booking_end_times', stdout=out)
    output = out.getvalue()
    
    # Should report that it fixed the booking
    assert "Scanned=1" in output
    assert "Fixed end_dt=1" in output
    assert "DryRun=False" in output
    
    # Verify booking was modified correctly
    booking.refresh_from_db()
    expected_end = start_time + timedelta(minutes=60)
    assert booking.end_dt == expected_end


@pytest.mark.django_db
def test_backfill_schedule_links_matches_weekly():
    """Test backfill_schedule_links links weekly schedules correctly"""
    client = Client.objects.create(
        name="Test Client",
        email="schedule1@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    service = Service.objects.create(
        code="walk30",
        name="30 Min Walk",
        duration_minutes=30,
        is_active=True
    )
    
    # Create a complete weekly schedule
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_weekly123",
        client=client,
        service_code=service.code,
        active=True
    )
    schedule = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="mon",
        default_time="10:00",
        days="MON",
        start_time="10:00",
        location="Test Location",
        repeats=StripeSubscriptionSchedule.REPEATS_WEEKLY
    )
    
    # Create a booking that matches the schedule
    # Use timezone-aware datetime as bookings would have
    from zoneinfo import ZoneInfo
    BRISBANE = ZoneInfo("Australia/Brisbane")
    monday_10am = datetime(2025, 1, 6, 10, 0)  # Naive datetime
    monday_10am_aware = timezone.make_aware(monday_10am, timezone=BRISBANE)
    
    booking = Booking.objects.create(
        client=client,
        service=service,
        service_code=service.code,
        service_name=service.name,
        service_label="Test Walk",
        start_dt=monday_10am_aware,
        end_dt=monday_10am_aware + timedelta(minutes=30),
        location="Test Location",
        status="confirmed",
        schedule=None  # No schedule link yet
    )
    
    out = StringIO()
    call_command('backfill_schedule_links', stdout=out)
    output = out.getvalue()
    
    # Should link the booking
    assert "Scanned=1" in output
    assert "Linked=1" in output
    
    # Verify booking was linked
    booking.refresh_from_db()
    assert booking.schedule == schedule


@pytest.mark.django_db
def test_backfill_schedule_links_skips_fortnightly():
    """Test backfill_schedule_links skips fortnightly schedules (ambiguous)"""
    client = Client.objects.create(
        name="Test Client",
        email="schedule2@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    service = Service.objects.create(
        code="walk30",
        name="30 Min Walk",
        duration_minutes=30,
        is_active=True
    )
    
    # Create a fortnightly schedule
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_fortnightly123",
        client=client,
        service_code=service.code,
        active=True
    )
    schedule = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="mon",
        default_time="10:00",
        days="MON",
        start_time="10:00",
        location="Test Location",
        repeats=StripeSubscriptionSchedule.REPEATS_FORTNIGHTLY
    )
    
    # Create a booking that would match if it were weekly
    from zoneinfo import ZoneInfo
    BRISBANE = ZoneInfo("Australia/Brisbane")
    monday_10am = datetime(2025, 1, 6, 10, 0)
    monday_10am_aware = timezone.make_aware(monday_10am, timezone=BRISBANE)
    
    booking = Booking.objects.create(
        client=client,
        service=service,
        service_code=service.code,
        service_name=service.name,
        service_label="Test Walk",
        start_dt=monday_10am_aware,
        end_dt=monday_10am_aware + timedelta(minutes=30),
        location="Test Location",
        status="confirmed",
        schedule=None
    )
    
    out = StringIO()
    call_command('backfill_schedule_links', stdout=out)
    output = out.getvalue()
    
    # Should NOT link the booking (fortnightly is ambiguous)
    assert "Scanned=1" in output
    assert "Linked=0" in output
    
    # Verify booking was NOT linked
    booking.refresh_from_db()
    assert booking.schedule is None


@pytest.mark.django_db
def test_diagnose_data_empty_database():
    """Test diagnose_data command with empty database"""
    out = StringIO()
    call_command('diagnose_data', stdout=out)
    output = out.getvalue()
    
    assert "=== Diagnostics ===" in output
    assert "Bookings: total=0" in output
    assert "Services: total=0" in output
    assert "Schedules: total=0" in output
    assert "StripePriceMap: total=0" in output
    assert "Tip:" in output


@pytest.mark.django_db
def test_diagnose_data_with_issues():
    """Test diagnose_data command reports issues correctly"""
    # Create test data with issues
    client = Client.objects.create(
        name="Test Client",
        email="diagnose@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    
    # Service without duration (issue)
    service_no_duration = Service.objects.create(
        code="walk",
        name="Walk",
        duration_minutes=None,
        is_active=True
    )
    
    # Service with duration (OK)
    service_ok = Service.objects.create(
        code="walk30",
        name="30 Min Walk",
        duration_minutes=30,
        is_active=True
    )
    
    # Booking with wrong end_dt (issue - would be caught by backfill_booking_end_times)
    now = timezone.now()
    Booking.objects.create(
        client=client,
        service=service_ok,
        service_code=service_ok.code,
        service_name=service_ok.name,
        service_label="Test Walk",
        start_dt=now,
        end_dt=now + timedelta(minutes=60),  # Wrong - should be 30
        location="Test Park",
        status="confirmed"
    )
    
    # Booking that requires review (issue)
    Booking.objects.create(
        client=client,
        service=service_ok,
        service_code=service_ok.code,
        service_name=service_ok.name,
        service_label="Test Walk",
        start_dt=now,
        end_dt=now + timedelta(minutes=30),
        location="Test Park",
        status="confirmed",
        requires_admin_review=True
    )
    
    out = StringIO()
    call_command('diagnose_data', stdout=out)
    output = out.getvalue()
    
    assert "Bookings: total=2" in output
    assert "review_flags=1" in output
    assert "Services: total=2" in output
    assert "without_duration=1" in output


@pytest.mark.django_db
def test_list_unmapped_prices_with_mock_stripe():
    """Test list_unmapped_prices command with mocked Stripe API"""
    out = StringIO()
    
    # Create a mapped price
    service = Service.objects.create(
        code="walk30",
        name="30 Min Walk",
        duration_minutes=30,
        is_active=True
    )
    StripePriceMap.objects.create(
        price_id="price_mapped123",
        service=service,
        active=True
    )
    
    # Mock Stripe API
    with patch('core.management.commands.list_unmapped_prices.stripe') as mock_stripe:
        # Create mock invoice with unmapped price
        mock_price = MagicMock()
        mock_price.id = "price_unmapped456"
        mock_price.nickname = "Test Unmapped Service"
        mock_price.product = MagicMock()
        mock_price.product.id = "prod_123"
        
        mock_line_item = MagicMock()
        mock_line_item.price = mock_price
        mock_line_item.description = "Test Service"
        
        mock_lines = MagicMock()
        mock_lines.data = [mock_line_item]
        
        mock_invoice = MagicMock()
        mock_invoice.id = "inv_123"
        mock_invoice.lines = mock_lines
        
        mock_list_result = MagicMock()
        mock_list_result.data = [mock_invoice]
        mock_list_result.has_more = False
        
        mock_stripe.Invoice.list.return_value = mock_list_result
        
        call_command('list_unmapped_prices', '--days', '30', stdout=out)
        output = out.getvalue()
        
        # Should report the unmapped price
        assert "price_unmapped456" in output
        assert "Test Unmapped Service" in output or "Test Service" in output


@pytest.mark.django_db
def test_list_unmapped_prices_all_mapped():
    """Test list_unmapped_prices when all prices are mapped"""
    out = StringIO()
    
    with patch('core.management.commands.list_unmapped_prices.stripe') as mock_stripe:
        # Mock empty invoice list
        mock_list_result = MagicMock()
        mock_list_result.data = []
        mock_list_result.has_more = False
        
        mock_stripe.Invoice.list.return_value = mock_list_result
        
        call_command('list_unmapped_prices', stdout=out)
        output = out.getvalue()
        
        # Should report all mapped
        assert "All Prices in the window are mapped" in output


@pytest.mark.django_db
def test_backfill_invoice_links_calls_sync():
    """Test backfill_invoice_links command calls sync_invoices"""
    out = StringIO()
    
    with patch('core.management.commands.backfill_invoice_links.sync_invoices') as mock_sync:
        mock_sync.return_value = {"created": 0, "updated": 0}
        
        call_command('backfill_invoice_links', '--days', '30', stdout=out)
        output = out.getvalue()
        
        # Should call sync_invoices with correct days parameter
        mock_sync.assert_called_once_with(days=30)
        assert "backfill_invoice_links complete" in output
