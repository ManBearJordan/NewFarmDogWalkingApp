from core import stripe_integration as si
import os

def test_get_api_key_missing(monkeypatch):
    monkeypatch.delenv('STRIPE_SECRET_KEY', raising=False)
    try:
        import pytest
        with pytest.raises(RuntimeError):
            si.list_active_subscriptions()
    except ImportError:
        pass