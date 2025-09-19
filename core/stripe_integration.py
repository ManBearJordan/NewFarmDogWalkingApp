"""Simplified Stripe integration helper.
Reads Stripe secret from STRIPE_SECRET_KEY env var first, optional keyring fallback.
Exposes get_api_key() and list_active_subscriptions().
"""
import os
import stripe
from typing import Optional

def get_api_key(env_var_name: str = 'STRIPE_SECRET_KEY') -> Optional[str]:
    key = os.getenv(env_var_name)
    if key:
        return key
    # Optional: fallback to keyring if installed
    try:
        import keyring
        k = keyring.get_password('NewFarmDogWalkingApp', 'stripe_secret_key')
        if k:
            return k
    except Exception:
        pass
    # Optional: fallback to Django model
    try:
        from core.models import StripeSettings
        k = StripeSettings.get_stripe_key()
        if k:
            return k
    except Exception:
        pass
    return None

def list_active_subscriptions(api_key: Optional[str] = None, **params):
    key = api_key or get_api_key()
    if not key:
        raise RuntimeError('Stripe API key not configured. Set STRIPE_SECRET_KEY in env or store via admin.')
    stripe.api_key = key
    return stripe.Subscription.list(**params)