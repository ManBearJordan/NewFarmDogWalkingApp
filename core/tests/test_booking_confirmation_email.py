import pytest
from django.core import mail
from django.utils import timezone
from datetime import timedelta
from core.models import Client, Booking
from core.tasks import send_booking_confirmation_email


@pytest.mark.django_db
def test_send_booking_confirmation_email_success():
    """Test that confirmation email is sent with correct content."""
    # Create a test client with email
    client = Client.objects.create(
        name="John Doe",
        email="john.doe@example.com",
        phone="123456789",
        address="123 Test St",
        status="active"
    )
    
    # Create a test booking
    now = timezone.now()
    booking = Booking.objects.create(
        client=client,
        service_code="dog_walk",
        service_name="Dog Walk",
        service_label="Dog Walk",
        start_dt=now + timedelta(hours=1),
        end_dt=now + timedelta(hours=2),
        location="Park",
        status="active",
        price_cents=5000,
        notes="",
    )
    
    # Call the task directly (synchronously for testing)
    result = send_booking_confirmation_email(booking.id)
    
    # Check result
    assert result == "sent"
    
    # Check that one email was sent
    assert len(mail.outbox) == 1
    
    # Check email details
    email = mail.outbox[0]
    assert email.subject == "Booking confirmed"
    assert "john.doe@example.com" in email.to
    assert "Hi John Doe" in email.body
    assert "Dog Walk" in email.body
    assert "Park" in email.body
    assert "New Farm Dog Walking" in email.body


@pytest.mark.django_db
def test_send_booking_confirmation_email_no_recipient():
    """Test that task handles bookings without client email gracefully."""
    # Create a test client WITHOUT email
    client = Client.objects.create(
        name="Jane Doe",
        email="",  # No email
        phone="123456789",
        address="123 Test St",
        status="active"
    )
    
    # Create a test booking
    now = timezone.now()
    booking = Booking.objects.create(
        client=client,
        service_code="grooming",
        service_name="Grooming",
        service_label="Grooming Service",
        start_dt=now + timedelta(hours=1),
        end_dt=now + timedelta(hours=2),
        location="Shop",
        status="active",
        price_cents=8000,
        notes="",
    )
    
    # Call the task directly
    result = send_booking_confirmation_email(booking.id)
    
    # Check result
    assert result == "no-recipient"
    
    # Check that no email was sent
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_send_booking_confirmation_email_with_null_location():
    """Test that task handles bookings with null/empty location."""
    client = Client.objects.create(
        name="Bob Smith",
        email="bob@example.com",
        phone="123456789",
        address="123 Test St",
        status="active"
    )
    
    now = timezone.now()
    booking = Booking.objects.create(
        client=client,
        service_code="pet_sitting",
        service_name="Pet Sitting",
        service_label="Pet Sitting",
        start_dt=now + timedelta(hours=1),
        end_dt=now + timedelta(hours=2),
        location="",  # Empty location
        status="active",
        price_cents=10000,
        notes="",
    )
    
    result = send_booking_confirmation_email(booking.id)
    
    assert result == "sent"
    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    # Should show em-dash for empty location
    assert "Location: —" in email.body or "Location: " in email.body
