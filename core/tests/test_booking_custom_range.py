import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from zoneinfo import ZoneInfo
from core.models import Client, Booking

TZ = ZoneInfo("Australia/Brisbane")

@pytest.fixture
def authed(client):
    u = User.objects.create_user(username="u", password="p")
    client.login(username="u", password="p")
    return client

@pytest.mark.django_db
def test_custom_range_filters_bookings(authed):
    cl = Client.objects.create(name="Alice")
    # Three bookings in spread dates
    b1 = Booking.objects.create(client=cl, service_code="walk", start_dt=timezone.datetime(2025,9,1,10,0,tzinfo=TZ), end_dt=timezone.datetime(2025,9,1,11,0,tzinfo=TZ), status="confirmed")
    b2 = Booking.objects.create(client=cl, service_code="walk", start_dt=timezone.datetime(2025,9,15,10,0,tzinfo=TZ), end_dt=timezone.datetime(2025,9,15,11,0,tzinfo=TZ), status="confirmed")
    b3 = Booking.objects.create(client=cl, service_code="walk", start_dt=timezone.datetime(2025,10,1,10,0,tzinfo=TZ), end_dt=timezone.datetime(2025,10,1,11,0,tzinfo=TZ), status="confirmed")
    url = reverse("booking_list")
    # Custom: 2025-09-01 .. 2025-09-30 should include b1 and b2 only
    resp = authed.get(url + "?range=custom&start=2025-09-01&end=2025-09-30")
    html = resp.content.decode()
    # Check for booking checkboxes specifically to avoid matching other content
    assert f'value="{b1.id}"' in html and f'value="{b2.id}"' in html and f'value="{b3.id}"' not in html