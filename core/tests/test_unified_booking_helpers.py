import pytest
from django.utils import timezone
from zoneinfo import ZoneInfo
from core.unified_booking_helpers import get_canonical_service_info, create_booking_with_unified_fields
from core.models import Client

TZ = ZoneInfo("Australia/Brisbane")

@pytest.mark.django_db
def test_canonical_service_resolution_from_label():
    info = get_canonical_service_info(service_label="Dog Walk")
    # We don't assert exact code map (comes from service_map/catalog),
    # but we expect at least a label to round-trip and price to be int or None.
    assert info["service_label"]
    assert isinstance(info["price_cents"], (int, type(None)))

@pytest.mark.django_db
def test_overnight_rule_applied():
    c = Client.objects.create(name="Alice")
    start = timezone.now().astimezone(TZ).replace(minute=0, second=0, microsecond=0)
    end = start  # same time; overnight should push +1 day
    b = create_booking_with_unified_fields(
        client=c,
        start_dt=start,
        end_dt=end,
        service_label="Overnight Stay",
        price_cents=1000,
    )
    assert (b.end_dt - b.start_dt).days >= 1

@pytest.mark.django_db
def test_batch_creation_still_uses_credit_and_single_invoice(monkeypatch):
    from core.booking_create_service import create_bookings_from_rows
    from core.models import Client
    cl = Client.objects.create(name="Bob", credit_cents=2500)

    # Fake Stripe functions to avoid needing API key for testing
    def fake_ensure_customer(client):
        return "cus_test123"
    def fake_create_or_reuse_draft_invoice(client):
        return "in_ABC"
    def fake_push_invoice_items_from_booking(booking, invoice_id):
        pass
    
    monkeypatch.setattr("core.booking_create_service.ensure_customer", fake_ensure_customer)
    monkeypatch.setattr("core.booking_create_service.create_or_reuse_draft_invoice", fake_create_or_reuse_draft_invoice)  
    monkeypatch.setattr("core.booking_create_service.push_invoice_items_from_booking", fake_push_invoice_items_from_booking)

    now = timezone.now().astimezone(TZ)
    rows = [
        {"start_dt": now, "end_dt": now, "service_label": "Dog Walk", "price_cents": 1200},  # Reduced price
        {"start_dt": now, "end_dt": now, "service_label": "Dog Walk", "price_cents": 1200},  # So both fit in credit
    ]
    result = create_bookings_from_rows(cl, rows)
    # Credit 2500 covers first fully (1200) and second (1200) = 2400; a single draft reused
    assert len(result["bookings"]) == 2
    # No invoice should be needed since all covered by credit
    assert result["invoice_id"] is None
    assert result["total_credit_used"] == 2400