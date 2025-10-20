import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from core.models import Client, Booking, Service


@pytest.mark.django_db
def test_client_dashboard_without_linked_client(client):
    """Test dashboard shows message when no client profile is linked"""
    user = User.objects.create_user(username="testuser", password="testpass")
    client.login(username="testuser", password="testpass")
    
    resp = client.get(reverse("portal_home"))
    assert resp.status_code == 200
    # Message should be added to Django messages framework
    messages = list(resp.context['messages'])
    assert len(messages) > 0
    assert "linked to a client record" in str(messages[0]).lower()


@pytest.mark.django_db
def test_client_dashboard_with_linked_client(client):
    """Test dashboard shows upcoming bookings for linked client"""
    user = User.objects.create_user(username="testuser", password="testpass")
    client_obj = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="1234567890",
        address="Test Address",
        status="active",
        user=user
    )
    service = Service.objects.create(
        code="walk30",
        name="30 Minute Walk",
        duration_minutes=30,
        is_active=True
    )
    
    # Create a future booking
    future_time = timezone.now() + timedelta(days=1)
    Booking.objects.create(
        client=client_obj,
        service=service,
        service_code=service.code,
        service_name=service.name,
        service_label=service.name,
        start_dt=future_time,
        end_dt=future_time + timedelta(minutes=30),
        status="active",
        price_cents=3000,
        location="Test Location",
        deleted=False
    )
    
    client.login(username="testuser", password="testpass")
    resp = client.get(reverse("portal_home"))
    assert resp.status_code == 200
    assert resp.context['client'] == client_obj
    assert len(resp.context['upcoming']) == 1


@pytest.mark.django_db
def test_client_calendar_without_linked_client(client):
    """Test calendar redirects to portal home when no client profile is linked"""
    user = User.objects.create_user(username="testuser", password="testpass")
    client.login(username="testuser", password="testpass")
    
    resp = client.get(reverse("calendar"))
    assert resp.status_code == 302
    assert resp.url == reverse("portal_home")


@pytest.mark.django_db
def test_client_calendar_with_linked_client(client):
    """Test calendar shows bookings for linked client"""
    user = User.objects.create_user(username="testuser", password="testpass")
    client_obj = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="1234567890",
        address="Test Address",
        status="active",
        user=user
    )
    
    client.login(username="testuser", password="testpass")
    resp = client.get(reverse("calendar"))
    assert resp.status_code == 200
    assert b"Calendar" in resp.content


@pytest.mark.django_db
def test_booking_create_without_linked_client(client):
    """Test booking create redirects when no client profile is linked"""
    user = User.objects.create_user(username="testuser", password="testpass")
    client.login(username="testuser", password="testpass")
    
    resp = client.get(reverse("portal_booking_create"))
    assert resp.status_code == 302
    assert resp.url == reverse("portal_home")


@pytest.mark.django_db
def test_booking_create_with_linked_client(client):
    """Test booking create shows form for linked client"""
    user = User.objects.create_user(username="testuser", password="testpass")
    client_obj = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="1234567890",
        address="Test Address",
        status="active",
        user=user
    )
    service = Service.objects.create(
        code="walk30",
        name="30 Minute Walk",
        duration_minutes=30,
        is_active=True
    )
    
    client.login(username="testuser", password="testpass")
    resp = client.get(reverse("portal_booking_create"))
    assert resp.status_code == 200
    # Check that the service is rendered in the page
    assert b"30 Minute Walk" in resp.content or b"walk30" in resp.content


@pytest.mark.django_db
def test_booking_confirm_without_session_data(client):
    """Test booking confirm redirects when no pending booking in session"""
    user = User.objects.create_user(username="testuser", password="testpass")
    client_obj = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="1234567890",
        address="Test Address",
        status="active",
        user=user
    )
    
    client.login(username="testuser", password="testpass")
    resp = client.get(reverse("portal_booking_confirm"))
    assert resp.status_code == 302
    # Should redirect to booking create page
    assert "portal" in resp.url or "book" in resp.url


@pytest.mark.django_db
def test_booking_create_post_creates_session(client):
    """Test booking create POST stores data in session"""
    user = User.objects.create_user(username="testuser", password="testpass")
    client_obj = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="1234567890",
        address="Test Address",
        status="active",
        user=user
    )
    service = Service.objects.create(
        code="walk30",
        name="30 Minute Walk",
        duration_minutes=30,
        is_active=True
    )
    
    client.login(username="testuser", password="testpass")
    resp = client.post(reverse("portal_booking_create"), {
        "service_id": str(service.id),
        "start": "2025-10-25T14:30:00"
    }, follow=False)
    
    # Debug output
    print(f'Status code: {resp.status_code}')
    if resp.status_code != 302:
        messages = list(resp.context.get('messages', [])) if hasattr(resp, 'context') and resp.context else []
        print(f'Messages: {[str(m) for m in messages]}')
        print(f'Service ID: {service.id}')
        print(f'Service active: {service.is_active}')
        print(f'Service duration: {service.duration_minutes}')
        print(f'Content: {resp.content[:1000]}')
    
    assert resp.status_code == 302
    assert resp.url == reverse("portal_booking_confirm")

