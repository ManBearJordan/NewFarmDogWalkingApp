import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from zoneinfo import ZoneInfo
from core.models import Client, SubOccurrence, Booking

TZ = ZoneInfo("Australia/Brisbane")

@pytest.mark.django_db
def test_overlap_blocked_when_only_active_hold_exists(client, monkeypatch):
    # Auth + client (same as existing test)
    u = User.objects.create_user(username="alice", password="p")
    c = Client.objects.create(name="Alice", user=u, credit_cents=5000)
    client.login(username="alice", password="p")
    # Mock catalog to provide a service (same as existing test)
    from core import stripe_integration
    monkeypatch.setattr(stripe_integration, "list_booking_services", lambda force_refresh=False: [
        {"price_id":"price_X","display_name":"Dog Walk","service_code":"walk","amount_cents":1500}
    ])
    # Create active hold overlapping the requested time (no bookings)
    start = timezone.datetime(2025,9,26,10,0,tzinfo=TZ)
    end   = timezone.datetime(2025,9,26,11,0,tzinfo=TZ)
    SubOccurrence.objects.create(stripe_subscription_id="sub_123", start_dt=start, end_dt=end, active=True)
    
    # Count bookings before
    bookings_before = Booking.objects.count()
    
    # Try to book inside that window (same format as existing test)
    resp = client.post(reverse("portal_booking_create"), {
        "service_price_id": "price_X",
        "start_dt": "2025-09-26T10:15",
        "end_dt":   "2025-09-26T10:45",
        "location": "Park",
        "notes": "",
    })
    
    # The response should be a form with error messages (status 200 but form re-rendered)
    assert resp.status_code == 200
    
    # No booking should have been created (blocked by overlap)
    bookings_after = Booking.objects.count()
    assert bookings_after == bookings_before  # Booking was blocked