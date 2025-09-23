import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from zoneinfo import ZoneInfo
from core.models import Client, Booking, SubOccurrence

TZ = ZoneInfo("Australia/Brisbane")

@pytest.fixture
def authed_client(client):
    u = User.objects.create_user(username="alice", password="p")
    c = Client.objects.create(name="Alice", user=u, credit_cents=2000)
    client.login(username="alice", password="p")
    return client, c

@pytest.mark.django_db
def test_booking_form_requires_login(client):
    resp = client.get(reverse("portal_booking_create"))
    assert resp.status_code in (302, 301)

@pytest.mark.django_db
def test_booking_overlap_blocked(authed_client, monkeypatch):
    client, c = authed_client
    # Mock catalog
    from core import stripe_integration
    monkeypatch.setattr(stripe_integration, "list_booking_services", lambda force_refresh=False: [
        {"price_id":"price_X","display_name":"Dog Walk","service_code":"walk","amount_cents":1500}
    ])
    # Existing booking overlaps
    start = timezone.datetime(2025,9,24,10,0,tzinfo=TZ)
    end   = timezone.datetime(2025,9,24,11,0,tzinfo=TZ)
    Booking.objects.create(client=c, service_code="walk", start_dt=start, end_dt=end, status="confirmed")
    resp = client.post(reverse("portal_booking_create"), {
        "service_price_id": "price_X",
        "start_dt": "2025-09-24T10:30",
        "end_dt": "2025-09-24T11:30",
        "location": "Park",
        "notes": "",
    })
    assert resp.status_code == 200
    assert b"not available" in resp.content

@pytest.mark.django_db
def test_booking_credit_covered_confirmation(authed_client, monkeypatch):
    client, c = authed_client
    from core import stripe_integration
    # Mock catalog
    monkeypatch.setattr(stripe_integration, "list_booking_services", lambda force_refresh=False: [
        {"price_id":"price_Y","display_name":"Dog Walk","service_code":"walk","amount_cents":1500}
    ])
    # Prevent real Stripe invoice calls by ensuring booking flow doesn't crash
    # (create_bookings_from_rows should handle credit-first, so no invoice created)
    start = timezone.datetime(2025,9,25,10,0,tzinfo=TZ)
    resp = client.post(reverse("portal_booking_create"), {
        "service_price_id": "price_Y",
        "start_dt": "2025-09-25T10:00",
        "end_dt": "2025-09-25T11:00",
        "location": "Park",
        "notes": "",
    }, follow=True)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "fully covered" in html.lower()

@pytest.mark.django_db
def test_booking_invoice_due_shows_public_link(authed_client, monkeypatch):
    client, c = authed_client
    from core import stripe_integration
    from core import credit
    # Mock catalog
    monkeypatch.setattr(stripe_integration, "list_booking_services", lambda force_refresh=False: [
        {"price_id":"price_Z","display_name":"Overnight","service_code":"overnight","amount_cents":10000}
    ])
    # Force booking to end with an invoice id and public URL
    def fake_public(inv_id): return "https://pay.stripe.com/invoice/test123"
    monkeypatch.setattr(stripe_integration, "get_invoice_public_url", fake_public)
    # Mock Stripe functions to prevent real calls
    monkeypatch.setattr(stripe_integration, "ensure_customer", lambda client: "cus_test123")
    monkeypatch.setattr(stripe_integration, "create_or_reuse_draft_invoice", lambda client: "inv_test123")
    monkeypatch.setattr(stripe_integration, "push_invoice_items_from_booking", lambda booking, invoice_id: None)
    # Mock credit functions 
    monkeypatch.setattr(credit, "get_client_credit", lambda client: 0)
    monkeypatch.setattr(credit, "deduct_client_credit", lambda client, amount: None)
    # After POST, assert redirect to confirm and link present.
    start = timezone.datetime(2025,9,26,18,0,tzinfo=TZ)
    # Ensure client has 0 credit for invoice path
    c.credit_cents = 0
    c.save(update_fields=["credit_cents"])
    resp = client.post(reverse("portal_booking_create"), {
        "service_price_id": "price_Z",
        "start_dt": "2025-09-26T18:00",
        "end_dt": "2025-09-27T08:00",
        "location": "Home",
        "notes": "Overnight",
    }, follow=True)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "open invoice" in html.lower()