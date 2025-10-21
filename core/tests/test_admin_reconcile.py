"""
Tests for admin reconciliation tools (reconcile console).
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from zoneinfo import ZoneInfo
from django.urls import reverse
from django.contrib.auth.models import User
from django.test import Client
from core.models import Booking, Service
from core.models import Client as ClientModel
from django.utils import timezone

BRISBANE = ZoneInfo("Australia/Brisbane")


@pytest.mark.django_db
def test_reconcile_index_requires_staff():
    """Test that reconcile_index requires staff authentication"""
    # Regular user (non-staff)
    user = User.objects.create_user(username="user", password="p", is_staff=False)
    client = Client()
    client.login(username="user", password="p")
    
    resp = client.get(reverse("admin_reconcile"))
    # Should redirect to admin login (302) or forbidden
    assert resp.status_code in (302, 403)


@pytest.mark.django_db
def test_reconcile_index_staff_access():
    """Test that staff can access reconcile_index"""
    user = User.objects.create_user(username="staff", password="p", is_staff=True)
    client = Client()
    client.login(username="staff", password="p")
    
    # Mock Stripe calls
    with patch('core.admin_tools_reconcile._recent_invoices') as mock_recent:
        mock_recent.return_value = []
        resp = client.get(reverse("admin_reconcile"))
    
    assert resp.status_code == 200
    assert b"Reconciliation Console" in resp.content


@pytest.mark.django_db
def test_reconcile_index_shows_unlinked_bookings():
    """Test that reconcile_index displays bookings without invoice"""
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
    
    # Mock Stripe calls
    with patch('core.admin_tools_reconcile._recent_invoices') as mock_recent:
        mock_recent.return_value = []
        resp = client.get(reverse("admin_reconcile"))
    
    assert resp.status_code == 200
    assert str(booking.id).encode() in resp.content
    assert b"Test Client" in resp.content


@pytest.mark.django_db
def test_reconcile_index_excludes_bookings_with_invoice():
    """Test that reconcile_index excludes bookings with invoice from unlinked list"""
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
    
    # Mock Stripe calls
    with patch('core.admin_tools_reconcile._recent_invoices') as mock_recent:
        mock_recent.return_value = []
        resp = client.get(reverse("admin_reconcile"))
    
    assert resp.status_code == 200
    # Should not show this booking in unlinked section since it has an invoice
    assert b"Test Client With Invoice" not in resp.content


@pytest.mark.django_db
def test_reconcile_link_requires_staff():
    """Test that reconcile_link requires staff authentication"""
    user = User.objects.create_user(username="user", password="p", is_staff=False)
    client = Client()
    client.login(username="user", password="p")
    
    resp = client.post(reverse("admin_reconcile_link"), {"booking_id": 1, "invoice_id": "in_test"})
    # Should redirect to admin login (302) or forbidden
    assert resp.status_code in (302, 403)


@pytest.mark.django_db
def test_reconcile_link_updates_booking():
    """Test that reconcile_link links booking to invoice"""
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
    
    # Mock Stripe invoice
    mock_invoice = MagicMock()
    mock_invoice.id = 'in_test123'
    mock_invoice.status = 'paid'
    mock_invoice.invoice_pdf = 'https://example.com/invoice.pdf'
    mock_invoice.hosted_invoice_url = 'https://example.com/invoice'
    mock_invoice.status_transitions = MagicMock()
    mock_invoice.status_transitions.paid_at = int(datetime.now(tz=BRISBANE).timestamp())
    mock_invoice.lines = MagicMock()
    mock_invoice.lines.data = []
    
    client = Client()
    client.login(username="staff", password="p")
    
    with patch('stripe.Invoice.retrieve') as mock_retrieve, \
         patch('core.admin_tools_reconcile.process_invoice'):
        mock_retrieve.return_value = mock_invoice
        
        resp = client.post(
            reverse("admin_reconcile_link"),
            {"booking_id": booking.id, "invoice_id": "in_test123"}
        )
    
    # Should redirect back to reconcile index
    assert resp.status_code == 302
    assert resp.url == reverse("admin_reconcile")
    
    # Check booking was updated
    booking.refresh_from_db()
    assert booking.stripe_invoice_id == "in_test123"
    assert booking.stripe_invoice_status == "paid"


@pytest.mark.django_db
def test_reconcile_detach_clears_invoice():
    """Test that reconcile_detach clears invoice from booking"""
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
        email="test4@example.com",
        phone="555-8888",
        address="999 Test Rd",
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
        stripe_invoice_id="in_test123",
        stripe_invoice_status="paid",
        invoice_pdf_url="https://example.com/invoice.pdf"
    )
    
    client = Client()
    client.login(username="staff", password="p")
    
    resp = client.post(
        reverse("admin_reconcile_detach"),
        {"booking_id": booking.id}
    )
    
    # Should redirect back to reconcile index
    assert resp.status_code == 302
    assert resp.url == reverse("admin_reconcile")
    
    # Check invoice fields were cleared
    booking.refresh_from_db()
    assert booking.stripe_invoice_id is None
    assert booking.stripe_invoice_status is None
    assert booking.invoice_pdf_url is None


@pytest.mark.django_db
def test_reconcile_create_from_line_creates_booking():
    """Test that reconcile_create_from_line creates a booking from invoice line"""
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
        email="test5@example.com",
        phone="555-7777",
        address="888 Test Ln",
        status="active",
        stripe_customer_id="cus_test123"
    )
    
    # Mock Stripe invoice and line
    mock_invoice = MagicMock()
    mock_invoice.id = 'in_test123'
    mock_invoice.customer = 'cus_test123'
    mock_invoice.status = 'open'
    mock_invoice.invoice_pdf = 'https://example.com/invoice.pdf'
    mock_invoice.hosted_invoice_url = 'https://example.com/invoice'
    mock_invoice.status_transitions = MagicMock()
    mock_invoice.status_transitions.paid_at = None
    
    # Create mock line item with metadata
    mock_line = MagicMock()
    mock_line.id = 'li_test123'
    mock_line.metadata = {
        'service_code': 'walk30',
        'booking_start': datetime.now(tz=BRISBANE).isoformat(),
        'location': 'Park'
    }
    
    mock_invoice.lines = MagicMock()
    mock_invoice.lines.data = [mock_line]
    
    client = Client()
    client.login(username="staff", password="p")
    
    with patch('stripe.Invoice.retrieve') as mock_retrieve, \
         patch('core.admin_tools_reconcile.process_invoice'):
        mock_retrieve.return_value = mock_invoice
        
        resp = client.post(
            reverse("admin_reconcile_create_from_line"),
            {"invoice_id": "in_test123", "line_id": "li_test123"}
        )
    
    # Should redirect back to reconcile index
    assert resp.status_code == 302
    assert resp.url == reverse("admin_reconcile")
    
    # Verify booking was created
    bookings = Booking.objects.filter(client=test_client, service=service)
    assert bookings.count() == 1
    
    booking = bookings.first()
    assert booking.location == 'Park'
    assert booking.stripe_invoice_id == 'in_test123'
    assert booking.autogenerated is False
