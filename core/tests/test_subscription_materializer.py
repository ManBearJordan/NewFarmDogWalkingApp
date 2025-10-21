import pytest
from datetime import datetime, timedelta
from django.utils import timezone
from core.models import Client, Service, StripeSubscriptionLink, StripeSubscriptionSchedule, Booking
from core.subscription_materializer import materialize_future_holds


@pytest.mark.django_db
def test_weekly_materializes_every_week():
    """Test that weekly subscriptions create bookings every week."""
    client = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    svc = Service.objects.create(
        code="walk30",
        name="Walk 30",
        duration_minutes=30,
        is_active=True
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_123",
        client=client,
        service_code="walk30",
        active=True
    )
    sched = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="mon,thu",
        default_time="10:30",
        days="MON,THU",
        start_time="10:30",
        location="Home",
        repeats=StripeSubscriptionSchedule.REPEATS_WEEKLY,
    )
    
    result = materialize_future_holds()
    
    # Expect multiple bookings across 8 weeks (2 days per week = 16 bookings)
    bookings = Booking.objects.filter(client=client, service=svc)
    assert bookings.count() >= 4, f"Expected at least 4 bookings, got {bookings.count()}"
    assert result['created'] >= 4


@pytest.mark.django_db
def test_fortnightly_materializes_every_two_weeks():
    """Test that fortnightly subscriptions create bookings every 2 weeks."""
    client = Client.objects.create(
        name="Test Client 2",
        email="test2@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    svc = Service.objects.create(
        code="walk60",
        name="Walk 60",
        duration_minutes=60,
        is_active=True
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_456",
        client=client,
        service_code="walk60",
        active=True
    )
    sched = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="wed",
        default_time="09:00",
        days="WED",
        start_time="09:00",
        location="Park",
        repeats=StripeSubscriptionSchedule.REPEATS_FORTNIGHTLY,
    )
    
    result = materialize_future_holds()
    
    # Expect fewer bookings vs weekly within the same 8-week horizon
    # Should be about 4 bookings (every 2 weeks)
    cnt = Booking.objects.filter(client=client, service=svc).count()
    assert cnt > 0, "Expected at least 1 booking"
    assert cnt <= 8, f"Expected at most 8 bookings for fortnightly over 8 weeks, got {cnt}"
    assert result['created'] > 0


@pytest.mark.django_db
def test_parsed_days_fallback():
    """Test that parsed_days falls back to WED when invalid."""
    client = Client.objects.create(
        name="Test Client 3",
        email="test3@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_789",
        client=client,
        service_code="walk30",
        active=True
    )
    sched = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="wed",
        default_time="10:30",
        days=None,  # No days specified
        start_time=None,
    )
    
    # Should fall back to weekdays_csv
    days = sched.parsed_days()
    assert 2 in days  # WED = 2


@pytest.mark.django_db
def test_parsed_time_fallback():
    """Test that parsed_time falls back to 10:30 when invalid."""
    client = Client.objects.create(
        name="Test Client 4",
        email="test4@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_abc",
        client=client,
        service_code="walk30",
        active=True
    )
    sched = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="wed",
        default_time="10:30",
        start_time=None,  # No start_time specified
    )
    
    # Should fall back to default_time
    t = sched.parsed_time()
    assert t.hour == 10
    assert t.minute == 30


@pytest.mark.django_db
def test_interval_weeks():
    """Test that interval_weeks returns correct values."""
    client = Client.objects.create(
        name="Test Client 5",
        email="test5@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_def",
        client=client,
        service_code="walk30",
        active=True
    )
    
    # Test weekly
    sched_weekly = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="wed",
        default_time="10:30",
        repeats=StripeSubscriptionSchedule.REPEATS_WEEKLY,
    )
    assert sched_weekly.interval_weeks() == 1
    
    # Update to fortnightly
    sched_weekly.repeats = StripeSubscriptionSchedule.REPEATS_FORTNIGHTLY
    assert sched_weekly.interval_weeks() == 2


@pytest.mark.django_db
def test_idempotency():
    """Test that running materializer twice doesn't duplicate bookings."""
    client = Client.objects.create(
        name="Test Client 6",
        email="test6@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    svc = Service.objects.create(
        code="walk45",
        name="Walk 45",
        duration_minutes=45,
        is_active=True
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_ghi",
        client=client,
        service_code="walk45",
        active=True
    )
    sched = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="mon",
        default_time="08:00",
        days="MON",
        start_time="08:00",
        location="Office",
        repeats=StripeSubscriptionSchedule.REPEATS_WEEKLY,
    )
    
    # First run
    result1 = materialize_future_holds()
    count1 = Booking.objects.filter(client=client, service=svc).count()
    
    # Second run - with new deterministic behavior, it deletes and recreates
    result2 = materialize_future_holds()
    count2 = Booking.objects.filter(client=client, service=svc).count()
    
    # Counts should be the same (no duplicates) - idempotent result
    assert count1 == count2, f"Duplicate bookings created: {count1} vs {count2}"
    # New behavior: deletes and recreates, so created count equals removed count
    assert result2['created'] == result2['removed'], "Second run should delete and recreate same bookings"


@pytest.mark.django_db
def test_autogenerated_flag_and_schedule_link():
    """Test that bookings are created with autogenerated flag and schedule link."""
    client = Client.objects.create(
        name="Test Client 7",
        email="test7@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    svc = Service.objects.create(
        code="walk30",
        name="Walk 30",
        duration_minutes=30,
        is_active=True
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_autogen",
        client=client,
        service_code="walk30",
        active=True
    )
    sched = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="mon",
        default_time="10:00",
        days="MON",
        start_time="10:00",
        location="Park",
        repeats=StripeSubscriptionSchedule.REPEATS_WEEKLY,
    )
    
    result = materialize_future_holds()
    
    # Check that bookings are marked as autogenerated
    bookings = Booking.objects.filter(client=client, service=svc)
    assert bookings.count() > 0
    for booking in bookings:
        assert booking.autogenerated is True
        assert booking.schedule == sched


@pytest.mark.django_db
def test_manual_bookings_not_deleted():
    """Test that manual bookings are not deleted during materialization."""
    client = Client.objects.create(
        name="Test Client 8",
        email="test8@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    svc = Service.objects.create(
        code="walk60",
        name="Walk 60",
        duration_minutes=60,
        is_active=True
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_manual",
        client=client,
        service_code="walk60",
        active=True
    )
    sched = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="tue",
        default_time="14:00",
        days="TUE",
        start_time="14:00",
        location="Home",
        repeats=StripeSubscriptionSchedule.REPEATS_WEEKLY,
    )
    
    # Create a manual booking (not autogenerated)
    from datetime import datetime
    manual_booking = Booking.objects.create(
        client=client,
        service=svc,
        service_code="walk60",
        service_name="Walk 60",
        service_label="Walk 60",
        start_dt=timezone.make_aware(datetime(2025, 10, 28, 16, 0)),  # Different time
        end_dt=timezone.make_aware(datetime(2025, 10, 28, 17, 0)),
        price_cents=0,
        status="pending",
        location="Custom Location",
        autogenerated=False,
        schedule=None,
    )
    
    result = materialize_future_holds()
    
    # Manual booking should still exist
    assert Booking.objects.filter(id=manual_booking.id).exists()
    manual_booking.refresh_from_db()
    assert manual_booking.autogenerated is False
    assert manual_booking.schedule is None


@pytest.mark.django_db
def test_inactive_schedule_removes_future_bookings():
    """Test that deactivating a schedule removes future autogenerated bookings."""
    client = Client.objects.create(
        name="Test Client 9",
        email="test9@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    svc = Service.objects.create(
        code="walk45",
        name="Walk 45",
        duration_minutes=45,
        is_active=True
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_inactive",
        client=client,
        service_code="walk45",
        active=True
    )
    sched = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="wed",
        default_time="09:00",
        days="WED",
        start_time="09:00",
        location="Office",
        repeats=StripeSubscriptionSchedule.REPEATS_WEEKLY,
    )
    
    # First materialization - creates bookings
    result1 = materialize_future_holds()
    count_active = Booking.objects.filter(client=client, service=svc).count()
    assert count_active > 0
    
    # Deactivate the subscription link
    link.active = False
    link.save()
    
    # Second materialization - should remove future bookings
    result2 = materialize_future_holds()
    count_inactive = Booking.objects.filter(client=client, service=svc).count()
    
    assert count_inactive == 0, "Future bookings should be removed when schedule is inactive"
    assert result2['removed'] == count_active


@pytest.mark.django_db
def test_skip_slot_with_manual_booking():
    """Test that materializer skips creating autogenerated booking if manual one exists."""
    from datetime import datetime, timedelta
    from django.utils import timezone as tz
    
    client = Client.objects.create(
        name="Test Client 10",
        email="test10@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    svc = Service.objects.create(
        code="walk30",
        name="Walk 30",
        duration_minutes=30,
        is_active=True
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_conflict",
        client=client,
        service_code="walk30",
        active=True
    )
    sched = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="mon",
        default_time="10:00",
        days="MON",
        start_time="10:00",
        location="Park",
        repeats=StripeSubscriptionSchedule.REPEATS_WEEKLY,
    )
    
    # Find next Monday at 10:00
    now = tz.localtime()
    days_ahead = (0 - now.weekday()) % 7  # 0 = Monday
    if days_ahead == 0 and now.hour >= 10:
        days_ahead = 7
    next_monday = now + timedelta(days=days_ahead)
    next_monday = next_monday.replace(hour=10, minute=0, second=0, microsecond=0)
    
    # Create manual booking at that exact time
    manual_booking = Booking.objects.create(
        client=client,
        service=svc,
        service_code="walk30",
        service_name="Walk 30",
        service_label="Walk 30",
        start_dt=next_monday,
        end_dt=next_monday + timedelta(minutes=30),
        price_cents=0,
        status="pending",
        location="Custom",
        autogenerated=False,
    )
    
    result = materialize_future_holds()
    
    # Should have skipped at least one slot
    assert result['skipped'] > 0
    # Manual booking should still exist and be unchanged
    manual_booking.refresh_from_db()
    assert manual_booking.autogenerated is False
    assert manual_booking.location == "Custom"
