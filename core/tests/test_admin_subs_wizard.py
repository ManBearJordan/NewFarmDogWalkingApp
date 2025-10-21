import pytest
from django.test import Client as TestClient
from django.contrib.auth.models import User
from core.models import Client, Service, StripeSubscriptionLink, StripeSubscriptionSchedule
from core.subscription_materializer import materialize_future_holds


@pytest.mark.django_db
def test_missing_fields_returns_list():
    """Test that missing_fields returns the correct list of missing fields."""
    client = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_123",
        client=client,
        service_code="walk30",
        active=True
    )
    sched = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="wed",
        default_time="10:30",
        # Missing: days, start_time, location
    )
    
    missing = sched.missing_fields()
    assert "days" in missing
    assert "start_time" in missing
    assert "location" in missing
    assert "service_code" not in missing  # comes from link
    assert "repeats" not in missing  # has default


@pytest.mark.django_db
def test_is_complete_returns_false_for_incomplete():
    """Test that is_complete returns False when fields are missing."""
    client = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_123",
        client=client,
        service_code="walk30",
        active=True
    )
    sched = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="wed",
        default_time="10:30",
    )
    
    assert sched.is_complete() is False


@pytest.mark.django_db
def test_is_complete_returns_true_for_complete():
    """Test that is_complete returns True when all fields are set."""
    client = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_123",
        client=client,
        service_code="walk30",
        active=True
    )
    sched = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="wed",
        default_time="10:30",
        days="MON,THU",
        start_time="10:30",
        location="Home",
        repeats=StripeSubscriptionSchedule.REPEATS_WEEKLY,
    )
    
    assert sched.is_complete() is True


@pytest.mark.django_db
def test_clean_validates_days_format():
    """Test that clean validates the days field format."""
    from django.core.exceptions import ValidationError
    
    client = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_123",
        client=client,
        service_code="walk30",
        active=True
    )
    sched = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="wed",
        default_time="10:30",
        days="INVALID",  # invalid day
        start_time="10:30",
        location="Home",
    )
    
    with pytest.raises(ValidationError) as exc:
        sched.clean()
    assert "days" in exc.value.message_dict


@pytest.mark.django_db
def test_clean_validates_start_time_format():
    """Test that clean validates the start_time field format."""
    from django.core.exceptions import ValidationError
    
    client = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_123",
        client=client,
        service_code="walk30",
        active=True
    )
    sched = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="wed",
        default_time="10:30",
        days="MON",
        start_time="invalid",  # invalid time format
        location="Home",
    )
    
    with pytest.raises(ValidationError) as exc:
        sched.clean()
    assert "start_time" in exc.value.message_dict


@pytest.mark.django_db
def test_materializer_skips_incomplete_schedule():
    """Test that materializer skips incomplete schedules."""
    client = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    Service.objects.create(
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
    # Create incomplete schedule (missing days, start_time, location)
    sched = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="wed",
        default_time="10:30",
    )
    
    result = materialize_future_holds()
    
    # Should create zero bookings due to incomplete schedule
    assert result['created'] == 0


@pytest.mark.django_db
def test_unscheduled_view_requires_auth():
    """Test that unscheduled view requires staff authentication."""
    test_client = TestClient()
    response = test_client.get("/admin-tools/subs/unscheduled/")
    
    # Should redirect to login
    assert response.status_code == 302


@pytest.mark.django_db
def test_unscheduled_view_shows_incomplete_schedules():
    """Test that unscheduled view shows incomplete schedules."""
    # Create staff user
    user = User.objects.create_user(username="admin", password="test", is_staff=True)
    
    client = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_123",
        client=client,
        service_code="walk30",
        active=True
    )
    sched = StripeSubscriptionSchedule.objects.create(
        sub=link,
        weekdays_csv="wed",
        default_time="10:30",
    )
    
    test_client = TestClient()
    test_client.force_login(user)
    response = test_client.get("/admin-tools/subs/unscheduled/")
    
    assert response.status_code == 200
    assert "needs schedule" in response.content.decode()


@pytest.mark.django_db
def test_wizard_view_requires_auth():
    """Test that wizard view requires staff authentication."""
    client = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    link = StripeSubscriptionLink.objects.create(
        stripe_subscription_id="sub_123",
        client=client,
        service_code="walk30",
        active=True
    )
    
    test_client = TestClient()
    response = test_client.get(f"/admin-tools/subs/wizard/{link.id}/")
    
    # Should redirect to login
    assert response.status_code == 302


@pytest.mark.django_db
def test_wizard_view_creates_schedule():
    """Test that wizard view creates/updates schedule."""
    user = User.objects.create_user(username="admin", password="test", is_staff=True)
    
    client = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    Service.objects.create(
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
    
    test_client = TestClient()
    test_client.force_login(user)
    
    response = test_client.post(f"/admin-tools/subs/wizard/{link.id}/", {
        "service_code": "walk30",
        "days": "MON,THU",
        "start_time": "10:30",
        "repeats": "weekly",
        "location": "Home",
    })
    
    # Should redirect to unscheduled list on success
    assert response.status_code == 302
    
    # Verify schedule was updated
    link.refresh_from_db()
    sched = link.schedule
    assert sched.days == "MON,THU"
    assert sched.start_time == "10:30"
    assert sched.location == "Home"
    assert sched.repeats == "weekly"
    assert sched.is_complete() is True
