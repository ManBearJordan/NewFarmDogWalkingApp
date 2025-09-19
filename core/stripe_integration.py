"""Simplified Stripe integration helper.
This module reads the Stripe secret from STRIPE_SECRET_KEY environment variable.
It exposes a small function list_active_subscriptions(api_key=None) that uses the stripe library directly.
"""
import os
import stripe
from typing import Optional


def get_api_key(env_var_name: str = 'STRIPE_SECRET_KEY') -> Optional[str]:
    key = os.getenv(env_var_name)
    if key:
        return key
    # Optional: fallback to keyring if installed and configured
    try:
        import keyring
        k = keyring.get_password('NewFarmDogWalkingApp', 'stripe_secret_key')
        if k:
            return k
    except Exception:
        pass
    return None


def list_active_subscriptions(api_key: Optional[str] = None, **params):
    key = api_key or get_api_key()
    if not key:
        raise RuntimeError('Stripe API key not configured. Set STRIPE_SECRET_KEY in env')
    stripe.api_key = key
    return stripe.Subscription.list(**params)