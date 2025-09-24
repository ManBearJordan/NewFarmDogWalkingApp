import pytest
from core import stripe_integration as si
from core.models import Client, Booking
from django.contrib.auth.models import User
from django.utils import timezone

class Dummy(dict):
    def __getattr__(self, k): return self[k]

def _price(id, amt, nick, prod):
    return Dummy({"id": id, "unit_amount": amt, "nickname": nick, "product": prod})

def _prod(id, name, meta=None):
    return Dummy({"id": id, "name": name, "metadata": meta or {}})

@pytest.mark.django_db
def test_catalog_fetch_and_cache(monkeypatch):
    # Reset cache
    si._set_cache([])
    # Mock key + Price.list
    monkeypatch.setattr(si, "get_stripe_key", lambda: "sk_test_123")
    def fake_list(**kwargs):
        class Res:
            def auto_paging_iter(self, limit=100):
                yield _price("price_A", 1500, "Walk 30", _prod("prod_1", "Dog Walks", {"service_code":"walk"}))
        return Res()
    monkeypatch.setattr(si.stripe, "Price", Dummy(list=fake_list))
    first = si.list_booking_services(force_refresh=True)
    assert first and first[0]["service_code"] == "walk"
    # Break Stripe; cached result should still return
    monkeypatch.setattr(si.stripe, "Price", Dummy(list=lambda **k: (_ for _ in ()).throw(RuntimeError("boom"))))
    second = si.list_booking_services()
    assert second == first

@pytest.mark.django_db
def test_api_key_fallback_methods(monkeypatch):
    """Test get_api_key fallback to keyring and Django model"""
    import os
    # Clear env var
    monkeypatch.delenv('STRIPE_SECRET_KEY', raising=False)
    
    # Mock keyring fallback
    mock_keyring = Dummy(get_password=lambda service, username: "sk_test_keyring")
    monkeypatch.setattr("keyring.get_password", mock_keyring.get_password)
    
    key = si.get_api_key()
    assert key == "sk_test_keyring"

@pytest.mark.django_db
def test_no_api_key_configured(monkeypatch):
    """Test when no API key is available"""
    monkeypatch.delenv('STRIPE_SECRET_KEY', raising=False)
    # Mock keyring to fail
    def mock_keyring_fail(service, username):
        raise Exception("keyring fail")
    monkeypatch.setattr("keyring.get_password", mock_keyring_fail)
    
    # Should return None when no key available
    key = si.get_api_key()
    assert key is None

@pytest.mark.django_db
def test_ensure_customer_creates_new(monkeypatch):
    """Test ensure_customer creates new customer when none exists"""
    user = User.objects.create_user(username="test", password="p")
    client = Client.objects.create(name="Test Client", email="test@example.com", user=user)
    
    # Mock Stripe API
    monkeypatch.setattr(si, "get_stripe_key", lambda: "sk_test_123")
    
    # Mock search to return empty result (no existing customer)
    class EmptySearchResult:
        def auto_paging_iter(self, limit=1):
            return iter([])
    
    mock_customer = Dummy(id="cus_new123", email="test@example.com", phone=None, address=None)
    customer_mock = Dummy(
        search=lambda query, limit: EmptySearchResult(),
        create=lambda **kwargs: mock_customer
    )
    monkeypatch.setattr(si.stripe, "Customer", customer_mock)
    
    customer_id = si.ensure_customer(client)
    assert customer_id == "cus_new123"

@pytest.mark.django_db
def test_ensure_customer_retrieves_existing(monkeypatch):
    """Test ensure_customer finds existing customer by email"""
    user = User.objects.create_user(username="test", password="p")
    client = Client.objects.create(name="Test Client", email="test@example.com", user=user)
    
    # Mock Stripe API
    monkeypatch.setattr(si, "get_stripe_key", lambda: "sk_test_123")
    
    # Mock search to return existing customer
    class ExistingSearchResult:
        def auto_paging_iter(self, limit=1):
            return iter([{"id": "cus_existing123", "email": "test@example.com"}])
    
    customer_mock = Dummy(
        search=lambda query, limit: ExistingSearchResult(),
        modify=lambda id, **kwargs: Dummy(id=id)
    )
    monkeypatch.setattr(si.stripe, "Customer", customer_mock)
    
    customer_id = si.ensure_customer(client)
    assert customer_id == "cus_existing123"

@pytest.mark.django_db
def test_push_invoice_items_from_booking(monkeypatch):
    """Test adding booking items to invoice"""
    user = User.objects.create_user(username="test", password="p")
    client = Client.objects.create(
        name="Test Client", 
        email="test@example.com", 
        user=user,
        stripe_customer_id="cus_123"
    )
    booking = Booking.objects.create(
        client=client,
        service_code="walk",
        service_name="Dog Walk",
        start_dt=timezone.now(),
        end_dt=timezone.now() + timezone.timedelta(hours=1),
        price_cents=1500,
        status="confirmed"
    )
    
    # Mock Stripe API
    monkeypatch.setattr(si, "get_api_key", lambda: "sk_test_123")
    created_items = []
    def mock_create(**kwargs):
        created_items.append(kwargs)
        return Dummy(id="ii_123")
    monkeypatch.setattr(si.stripe, "InvoiceItem", Dummy(create=mock_create))
    
    si.push_invoice_items_from_booking(booking, "inv_123")
    assert len(created_items) == 1
    assert created_items[0]["customer"] == "cus_123"
    assert created_items[0]["amount"] == 1500