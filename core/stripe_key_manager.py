"""
Stripe key manager for core app.

Implements the required functions:
- get_stripe_key(): read from ENV first, fallback to DB model StripeSettings if present.
- get_key_status(): {configured: bool, mode: 'test'|'live'|None} based on key prefix.
- update_stripe_key(key:str): persist to DB (create/update single row).
"""
import os
from typing import Optional, Dict
from .models import StripeSettings


def get_stripe_key() -> Optional[str]:
    """Read from ENV first, fallback to DB model StripeSettings if present."""
    # Check environment variables first
    for name in ("STRIPE_SECRET_KEY", "STRIPE_API_KEY"):
        key = os.getenv(name)
        if key and key.strip():
            return key.strip()
    
    # Fallback to database
    try:
        db_key = StripeSettings.get_stripe_key()
        if db_key and db_key.strip():
            return db_key.strip()
    except Exception:
        pass
    
    return None


def get_key_status() -> Dict[str, Optional[object]]:
    """Return {configured: bool, mode: 'test'|'live'|None} based on key prefix."""
    key = get_stripe_key()
    
    if not key:
        return {
            'configured': False,
            'mode': None
        }
    
    mode = None
    if key.startswith('sk_test_'):
        mode = 'test'
    elif key.startswith('sk_live_'):
        mode = 'live'
    
    return {
        'configured': True,
        'mode': mode
    }


def update_stripe_key(key: str) -> None:
    """Persist to DB (create/update single row)."""
    if not key or not isinstance(key, str):
        raise ValueError("Key must be a non-empty string")
    
    key = key.strip()
    if not key:
        raise ValueError("Key must be a non-empty string")
    
    # Determine if it's live mode based on key prefix
    is_live = key.startswith('sk_live_')
    
    # Create or update the single StripeSettings row
    obj, created = StripeSettings.objects.get_or_create(
        defaults={
            'stripe_secret_key': key,
            'is_live_mode': is_live
        }
    )
    
    if not created:
        obj.stripe_secret_key = key
        obj.is_live_mode = is_live
        obj.save()