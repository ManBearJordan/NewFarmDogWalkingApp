import pytest
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from core.stripe_integration import list_booking_services, _CATALOG_CACHE, _set_cache

class DummyObj(dict):
    def __getattr__(self, k):  # helpful if a caller uses attr
        return self[k]

def _make_price(id, unit_amount, nickname, product):
    return DummyObj({
        "id": id,
        "unit_amount": unit_amount,
        "nickname": nickname,
        "product": product,  # expanded dict or product id string
    })

def _make_product(id, name, metadata=None):
    return DummyObj({
        "id": id,
        "name": name,
        "metadata": metadata or {},
    })

class StripeCatalogTestCase(TestCase):
    def test_catalog_maps_prices_and_uses_cache(self):
        # Reset cache
        _set_cache([])

        # Mock Stripe Price.list -> auto_paging_iter
        from core import stripe_integration
        def fake_list(**kwargs):
            class Res:
                def auto_paging_iter(self, limit=100):
                    yield _make_price("price_1", 1500, "Dog Walk", _make_product("prod_A", "Dog Services", {"service_code":"walk"}))
                    yield _make_price("price_2", 5000, None, _make_product("prod_B", "Overnight", {}))
            return Res()
        
        # Store original objects to restore later
        original_price = stripe_integration.stripe.Price
        original_get_key = stripe_integration.get_stripe_key
        
        try:
            stripe_integration.stripe.Price = DummyObj(list=fake_list)
            # A key is required by _fetch_catalog_from_stripe(); bypass _init_stripe by stubbing get_stripe_key
            stripe_integration.get_stripe_key = lambda: "sk_test_123"

            # First call hits Stripe
            items = list_booking_services(force_refresh=True)
            self.assertEqual(len(items), 2)
            self.assertEqual(items[0]["service_code"], "walk")
            self.assertEqual(items[0]["amount_cents"], 1500)
            self.assertIn(items[1]["display_name"], ("Overnight", "Service"))

            # Second call uses cache (no exception even if Stripe breaks)
            stripe_integration.stripe.Price = DummyObj(list=lambda **k: (_ for _ in ()).throw(RuntimeError("boom")))
            cached = list_booking_services(force_refresh=False)
            self.assertEqual(cached, items)
        finally:
            # Restore original objects
            stripe_integration.stripe.Price = original_price
            stripe_integration.get_stripe_key = original_get_key