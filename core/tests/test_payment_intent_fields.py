"""Tests for payment_intent_id and charge_id fields on Booking model."""
import pytest
from django.utils import timezone
from datetime import date, time
from core.models import Client, Booking


@pytest.mark.django_db
def test_booking_has_payment_intent_fields():
    """Test that Booking model has payment_intent_id and charge_id fields."""
    client = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="123456789",
        address="Test Address",
        status="active"
    )
    
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(timezone.datetime.combine(date.today(), time(10, 0)), tz)
    end_dt = timezone.make_aware(timezone.datetime.combine(date.today(), time(11, 0)), tz)
    
    booking = Booking.objects.create(
        client=client,
        service_code="walk",
        service_name="Dog Walk",
        service_label="Dog Walk",
        start_dt=start_dt,
        end_dt=end_dt,
        status="active",
        price_cents=5000,
        location="Park",
        payment_intent_id="pi_test_123456789",
        charge_id="ch_test_987654321"
    )
    
    assert booking.payment_intent_id == "pi_test_123456789"
    assert booking.charge_id == "ch_test_987654321"


@pytest.mark.django_db
def test_booking_payment_fields_nullable():
    """Test that payment_intent_id and charge_id can be null for invoice-based bookings."""
    client = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="123456789",
        address="Test Address",
        status="active"
    )
    
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(timezone.datetime.combine(date.today(), time(10, 0)), tz)
    end_dt = timezone.make_aware(timezone.datetime.combine(date.today(), time(11, 0)), tz)
    
    # Invoice-based booking (staff-created)
    booking = Booking.objects.create(
        client=client,
        service_code="walk",
        service_name="Dog Walk",
        service_label="Dog Walk",
        start_dt=start_dt,
        end_dt=end_dt,
        status="active",
        price_cents=5000,
        location="Park",
        stripe_invoice_id="in_123456789",
        # payment_intent_id and charge_id not set for invoice flow
    )
    
    assert booking.stripe_invoice_id == "in_123456789"
    assert booking.payment_intent_id is None
    assert booking.charge_id is None


@pytest.mark.django_db
def test_booking_portal_vs_staff_flow():
    """Test that we can distinguish portal (PI) vs staff (invoice) bookings."""
    client = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="123456789",
        address="Test Address",
        status="active"
    )
    
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(timezone.datetime.combine(date.today(), time(10, 0)), tz)
    end_dt = timezone.make_aware(timezone.datetime.combine(date.today(), time(11, 0)), tz)
    
    # Portal booking (has payment_intent_id, no invoice)
    portal_booking = Booking.objects.create(
        client=client,
        service_code="walk",
        service_name="Dog Walk",
        service_label="Dog Walk",
        start_dt=start_dt,
        end_dt=end_dt,
        status="active",
        price_cents=5000,
        location="Park",
        payment_intent_id="pi_test_123",
        charge_id="ch_test_456",
        stripe_invoice_id=None
    )
    
    # Staff booking (has invoice, no payment_intent)
    staff_booking = Booking.objects.create(
        client=client,
        service_code="walk",
        service_name="Dog Walk",
        service_label="Dog Walk",
        start_dt=start_dt + timezone.timedelta(days=1),
        end_dt=end_dt + timezone.timedelta(days=1),
        status="active",
        price_cents=5000,
        location="Park",
        stripe_invoice_id="in_test_789",
        payment_intent_id=None,
        charge_id=None
    )
    
    # Portal booking check
    assert portal_booking.payment_intent_id is not None
    assert portal_booking.stripe_invoice_id is None
    
    # Staff booking check
    assert staff_booking.stripe_invoice_id is not None
    assert staff_booking.payment_intent_id is None
