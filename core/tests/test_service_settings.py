import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.conf import settings
from core.models import Service, Client, Booking, SubOccurrence, StripeSubscriptionLink
from datetime import datetime, timedelta
from django.utils import timezone


@pytest.mark.django_db
def test_service_model_creation():
    """Test creating a Service model instance"""
    service = Service.objects.create(
        code="walk30",
        name="Standard Walk (30m)",
        duration_minutes=30,
        is_active=True
    )
    assert service.code == "walk30"
    assert service.name == "Standard Walk (30m)"
    assert service.duration_minutes == 30
    assert service.is_active is True
    assert "30m" in str(service)


@pytest.mark.django_db
def test_service_str_without_duration():
    """Test Service __str__ method without duration"""
    service = Service.objects.create(
        code="walk60",
        name="Extended Walk",
        is_active=True
    )
    assert str(service) == "Extended Walk"


@pytest.mark.django_db
def test_service_settings_requires_staff(client):
    """Test that service_settings view requires staff authentication"""
    # Anonymous user should redirect to login
    resp = client.get(reverse("service_settings"))
    assert resp.status_code == 302
    assert '/login' in resp.url or 'accounts/login' in resp.url
    
    # Regular user (not staff) should redirect to login
    user = User.objects.create_user(username="regularuser", password="testpass", is_staff=False)
    client.login(username="regularuser", password="testpass")
    resp = client.get(reverse("service_settings"))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_service_settings_staff_access(client):
    """Test that staff users can access service_settings view"""
    user = User.objects.create_user(username="staffuser", password="testpass", is_staff=True)
    client.login(username="staffuser", password="testpass")
    resp = client.get(reverse("service_settings"))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_service_settings_seeds_default_services(client):
    """Test that service_settings seeds default services on first visit"""
    user = User.objects.create_user(username="staffuser", password="testpass", is_staff=True)
    client.login(username="staffuser", password="testpass")
    
    # No services initially
    assert Service.objects.count() == 0
    
    # Visit the page
    resp = client.get(reverse("service_settings"))
    assert resp.status_code == 200
    
    # Should have seeded 3 services
    assert Service.objects.count() == 3
    assert Service.objects.filter(code="walk30").exists()
    assert Service.objects.filter(code="walk60").exists()
    assert Service.objects.filter(code="puppy30").exists()


@pytest.mark.django_db
def test_service_settings_post_updates_durations(client):
    """Test that POST request updates service durations"""
    user = User.objects.create_user(username="staffuser", password="testpass", is_staff=True)
    client.login(username="staffuser", password="testpass")
    
    # Create a service
    service = Service.objects.create(code="walk30", name="Walk 30")
    
    # Post form data
    post_data = {
        'form-TOTAL_FORMS': '1',
        'form-INITIAL_FORMS': '1',
        'form-MIN_NUM_FORMS': '0',
        'form-MAX_NUM_FORMS': '1000',
        'form-0-id': service.id,
        'form-0-code': 'walk30',
        'form-0-name': 'Walk 30',
        'form-0-duration_minutes': '30',
        'form-0-is_active': 'on',
    }
    
    resp = client.post(reverse("service_settings"), data=post_data)
    assert resp.status_code == 302  # Redirect after successful save
    
    # Check that duration was updated
    service.refresh_from_db()
    assert service.duration_minutes == 30


@pytest.mark.django_db
def test_booking_with_service():
    """Test creating a Booking with a Service"""
    client_obj = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="1234567890",
        address="123 Test St",
        status="active"
    )
    service = Service.objects.create(
        code="walk30",
        name="Standard Walk",
        duration_minutes=30,
        is_active=True
    )
    
    now = timezone.now()
    booking = Booking.objects.create(
        client=client_obj,
        service=service,
        service_code="walk30",
        service_name="Standard Walk",
        service_label="Standard Walk",
        start_dt=now,
        end_dt=now + timedelta(minutes=30),
        location="Park",
        dogs=1,
        status="confirmed",
        price_cents=3000
    )
    
    assert booking.service == service
    assert booking.service.duration_minutes == 30


@pytest.mark.django_db
def test_suboccurrence_with_service():
    """Test creating a SubOccurrence with a Service"""
    service = Service.objects.create(
        code="walk30",
        name="Standard Walk",
        duration_minutes=30,
        is_active=True
    )
    
    now = timezone.now()
    occ = SubOccurrence.objects.create(
        stripe_subscription_id="sub_123",
        start_dt=now,
        end_dt=now + timedelta(minutes=30),
        active=True,
        service=service
    )
    
    assert occ.service == service
    assert occ.service.duration_minutes == 30


@pytest.mark.django_db
def test_service_duration_guard_middleware_blocks_staff_without_durations(client):
    """Test that middleware redirects staff when active services have no duration"""
    user = User.objects.create_user(username="staffuser", password="testpass", is_staff=True)
    client.login(username="staffuser", password="testpass")
    
    # Create an active service without duration
    Service.objects.create(code="walk30", name="Walk 30", is_active=True)
    
    # Try to access a path that's not exempt (not in staff portal paths)
    # /admin-tools/ is not in the exempt list
    resp = client.get(reverse("admin_reconcile"))
    
    # Should redirect to service_settings
    assert resp.status_code == 302
    assert reverse("service_settings") in resp.url


@pytest.mark.django_db
def test_service_duration_guard_middleware_allows_staff_with_durations(client):
    """Test that middleware allows staff when all active services have durations"""
    user = User.objects.create_user(username="staffuser", password="testpass", is_staff=True)
    client.login(username="staffuser", password="testpass")
    
    # Create an active service with duration
    Service.objects.create(code="walk30", name="Walk 30", duration_minutes=30, is_active=True)
    
    # Should be able to access non-exempt pages
    resp = client.get(reverse("admin_reconcile"))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_service_duration_guard_middleware_ignores_inactive_services(client):
    """Test that middleware ignores inactive services without durations"""
    user = User.objects.create_user(username="staffuser", password="testpass", is_staff=True)
    client.login(username="staffuser", password="testpass")
    
    # Create an inactive service without duration
    Service.objects.create(code="walk30", name="Walk 30", is_active=False)
    
    # Should be able to access other pages (inactive services are ignored)
    resp = client.get(reverse("admin_reconcile"))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_service_duration_guard_middleware_allows_non_staff(client):
    """Test that middleware doesn't block non-staff users"""
    # Create user without staff privileges but with access
    user = User.objects.create_user(username="regularuser", password="testpass", is_staff=False)
    client.login(username="regularuser", password="testpass")
    
    # Create an active service without duration
    Service.objects.create(code="walk30", name="Walk 30", is_active=True)
    
    # Non-staff users should not be redirected by this middleware
    # (they may be blocked by other middleware/permissions)
    resp = client.get(reverse("portal_home"))
    # Just check that we don't get redirected to service_settings
    assert reverse("service_settings") not in resp.url if resp.status_code == 302 else True


@pytest.mark.django_db
def test_service_duration_guard_exempts_admin_path(client):
    """Test that middleware exempts the configured DJANGO_ADMIN_URL path"""
    # Create staff user
    user = User.objects.create_user(username="staffuser", password="testpass", is_staff=True, is_superuser=True)
    client.login(username="staffuser", password="testpass")
    
    # Create an active service without duration (would normally block staff)
    Service.objects.create(code="walk30", name="Walk 30", is_active=True)
    
    # Get the configured admin URL from settings
    admin_url = getattr(settings, 'DJANGO_ADMIN_URL', 'admin/')
    admin_path = f"/{admin_url.lstrip('/')}"
    
    # Access the admin path - should NOT be redirected to service_settings
    resp = client.get(admin_path)
    # Should either load admin (200) or redirect to admin login, but NOT to service_settings
    assert reverse("service_settings") not in resp.url if resp.status_code == 302 else True


@pytest.mark.django_db
def test_service_duration_guard_exempts_fallback_admin_path(client):
    """Test that middleware exempts the fallback /admin/ path"""
    # Create staff user
    user = User.objects.create_user(username="staffuser", password="testpass", is_staff=True, is_superuser=True)
    client.login(username="staffuser", password="testpass")
    
    # Create an active service without duration (would normally block staff)
    Service.objects.create(code="walk30", name="Walk 30", is_active=True)
    
    # Access the fallback /admin/ path - should NOT be redirected to service_settings
    resp = client.get("/admin/")
    # Should either load admin (200) or redirect to admin login, but NOT to service_settings
    assert reverse("service_settings") not in resp.url if resp.status_code == 302 else True


@pytest.mark.django_db
def test_service_duration_guard_still_blocks_non_admin_staff_paths(client):
    """Test that middleware still blocks staff from non-exempt paths when services need setup"""
    # Create staff user
    user = User.objects.create_user(username="staffuser", password="testpass", is_staff=True, is_superuser=True)
    client.login(username="staffuser", password="testpass")
    
    # Create an active service without duration
    Service.objects.create(code="walk30", name="Walk 30", is_active=True)
    
    # Try to access non-exempt paths - should be redirected to service_settings by our middleware
    non_exempt_paths = [
        reverse("admin_reconcile"),  # /admin-tools/ is not in the exempt list
    ]
    
    for path in non_exempt_paths:
        resp = client.get(path)
        assert resp.status_code == 302, f"Expected redirect for {path}"
        assert reverse("service_settings") in resp.url, f"Expected redirect to service_settings for {path}"
    
    # But exempt paths should NOT be redirected by our middleware
    # (the view itself may have its own logic, but our middleware should not intercept)
    exempt_paths = [
        reverse("client_list"),  # /clients/ is exempt
        reverse("booking_list"),  # /bookings/ is exempt
    ]
    
    for path in exempt_paths:
        resp = client.get(path)
        # Should NOT be redirected to service_settings by our middleware
        # (200 or other redirects are fine, just not to service_settings)
        assert resp.status_code == 200, f"Expected success for exempt path {path}"
