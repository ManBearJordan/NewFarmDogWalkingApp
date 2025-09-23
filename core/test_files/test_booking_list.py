import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import Client, Booking
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Australia/Brisbane")

@pytest.fixture
def authed(client):
    u = User.objects.create_user(username="u", password="p")
    client.login(username="u", password="p")
    return client

@pytest.mark.django_db
def test_booking_list_filters_and_delete(authed):
    cl = Client.objects.create(name="Alice", email="alice@test.com", phone="123-456-7890", address="Test Address", status="active")
    now = timezone.now().astimezone(TZ)
    b1 = Booking.objects.create(client=cl, service_code="walk", service_name="Walk", service_label="Walk",
                                start_dt=now, end_dt=now, location="Park", dogs=1, status="confirmed", price_cents=2000)
    b2 = Booking.objects.create(client=cl, service_code="walk", service_name="Walk", service_label="Walk",
                                start_dt=now, end_dt=now, location="Park", dogs=1, status="cancelled", price_cents=2000)
    html = authed.get(reverse("booking_list")).content.decode()
    # Check that confirmed booking appears and cancelled booking does not
    assert f'value="{b1.id}"' in html  # confirmed booking should appear (checkbox)
    assert f'value="{b2.id}"' not in html  # cancelled booking should not appear (checkbox)
    # delete
    authed.get(reverse("booking_soft_delete", args=[b1.id]))
    b1.refresh_from_db()
    assert b1.deleted is True

@pytest.mark.django_db
def test_booking_open_invoice_no_invoice(authed):
    """Test redirect when booking has no invoice."""
    cl = Client.objects.create(name="Bob", email="bob@test.com", phone="123-456-7890", address="Test Address", status="active")
    now = timezone.now().astimezone(TZ)
    b = Booking.objects.create(client=cl, service_code="walk", service_name="Walk", service_label="Walk",
                               start_dt=now, end_dt=now, location="", dogs=1, status="confirmed", price_cents=1000)
    # No stripe_invoice_id set
    resp = authed.get(reverse("booking_open_invoice", args=[b.id]))
    assert resp.status_code in (301, 302)  # Redirect back to list
    assert "/bookings/" in resp.headers["Location"]