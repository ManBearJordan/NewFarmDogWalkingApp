"""
Tests for admin reconciliation tools.
"""
import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.test import Client
from core.models import Booking, Service
from core.models import Client as ClientModel
from django.utils import timezone


@pytest.mark.django_db
def test_reconcile_list_requires_staff():
    """Test that reconcile_list requires staff authentication"""
    # Regular user (non-staff)
    user = User.objects.create_user(username="user", password="p", is_staff=False)
    client = Client()
    client.login(username="user", password="p")
    
    resp = client.get(reverse("admin_reconcile"))
    # Should redirect to admin login (302) or forbidden
    assert resp.status_code in (302, 403)


@pytest.mark.django_db
def test_reconcile_list_staff_access():
    """Test that staff can access reconcile_list"""
    user = User.objects.create_user(username="staff", password="p", is_staff=True)
    client = Client()
    client.login(username="staff", password="p")
    
    resp = client.get(reverse("admin_reconcile"))
    assert resp.status_code == 200
    assert b"Reconcile: Bookings without invoice" in resp.content


@pytest.mark.django_db
def test_reconcile_list_shows_bookings_without_invoice():
    """Test that reconcile_list displays bookings without invoice"""
    user = User.objects.create_user(username="staff", password="p", is_staff=True)
    
    # Create a service
    service = Service.objects.create(
        code="walk30",
        name="30min Walk",
        duration_minutes=30
    )
    
    # Create a client
    test_client = ClientModel.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="555-1234",
        address="123 Test St",
        status="active"
    )
    
    # Create booking without invoice
    booking = Booking.objects.create(
        client=test_client,
        service=service,
        service_code="walk30",
        service_name="30min Walk",
        service_label="30min Walk",
        start_dt=timezone.now(),
        end_dt=timezone.now() + timezone.timedelta(minutes=30),
        location="Test Location",
        status="confirmed",
        stripe_invoice_id=None
    )
    
    client = Client()
    client.login(username="staff", password="p")
    
    resp = client.get(reverse("admin_reconcile"))
    assert resp.status_code == 200
    assert str(booking.id).encode() in resp.content
    assert b"Test Client" in resp.content


@pytest.mark.django_db
def test_reconcile_list_excludes_bookings_with_invoice():
    """Test that reconcile_list excludes bookings with invoice"""
    user = User.objects.create_user(username="staff", password="p", is_staff=True)
    
    # Create a service
    service = Service.objects.create(
        code="walk30",
        name="30min Walk",
        duration_minutes=30
    )
    
    # Create a client
    test_client = ClientModel.objects.create(
        name="Test Client With Invoice",
        email="test2@example.com",
        phone="555-5678",
        address="456 Test Ave",
        status="active"
    )
    
    # Create booking with invoice
    booking = Booking.objects.create(
        client=test_client,
        service=service,
        service_code="walk30",
        service_name="30min Walk",
        service_label="30min Walk",
        start_dt=timezone.now(),
        end_dt=timezone.now() + timezone.timedelta(minutes=30),
        location="Test Location",
        status="confirmed",
        stripe_invoice_id="inv_12345"
    )
    
    client = Client()
    client.login(username="staff", password="p")
    
    resp = client.get(reverse("admin_reconcile"))
    assert resp.status_code == 200
    # Should not show this booking since it has an invoice
    assert b"Test Client With Invoice" not in resp.content


@pytest.mark.django_db
def test_reconcile_mark_paid_requires_staff():
    """Test that reconcile_mark_paid requires staff authentication"""
    user = User.objects.create_user(username="user", password="p", is_staff=False)
    client = Client()
    client.login(username="user", password="p")
    
    resp = client.get(reverse("admin_reconcile_paid", kwargs={"booking_id": 1}))
    # Should redirect to admin login (302) or forbidden
    assert resp.status_code in (302, 403)


@pytest.mark.django_db
def test_reconcile_mark_paid_updates_booking():
    """Test that reconcile_mark_paid updates booking status to paid"""
    user = User.objects.create_user(username="staff", password="p", is_staff=True)
    
    # Create a service
    service = Service.objects.create(
        code="walk30",
        name="30min Walk",
        duration_minutes=30
    )
    
    # Create a client
    test_client = ClientModel.objects.create(
        name="Test Client",
        email="test3@example.com",
        phone="555-9999",
        address="789 Test Blvd",
        status="active"
    )
    
    # Create booking
    booking = Booking.objects.create(
        client=test_client,
        service=service,
        service_code="walk30",
        service_name="30min Walk",
        service_label="30min Walk",
        start_dt=timezone.now(),
        end_dt=timezone.now() + timezone.timedelta(minutes=30),
        location="Test Location",
        status="confirmed"
    )
    
    client = Client()
    client.login(username="staff", password="p")
    
    resp = client.get(reverse("admin_reconcile_paid", kwargs={"booking_id": booking.id}))
    # Should redirect back to reconcile list
    assert resp.status_code == 302
    assert resp.url == reverse("admin_reconcile")
    
    # Check booking was updated
    booking.refresh_from_db()
    assert booking.payment_status == "paid"


@pytest.mark.django_db
def test_reconcile_mark_paid_invalid_booking():
    """Test that reconcile_mark_paid handles invalid booking ID"""
    user = User.objects.create_user(username="staff", password="p", is_staff=True)
    
    client = Client()
    client.login(username="staff", password="p")
    
    resp = client.get(reverse("admin_reconcile_paid", kwargs={"booking_id": 99999}))
    # Should redirect back to reconcile list
    assert resp.status_code == 302
    assert resp.url == reverse("admin_reconcile")
