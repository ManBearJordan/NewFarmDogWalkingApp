"""Very small helper: prefer environment variable as the single source of truth at runtime.
"""
import os


def get_stripe_key() -> str:
    return os.getenv('STRIPE_SECRET_KEY', '')


def set_stripe_key(key: str) -> bool:
    # For this clean skeleton we do not write keys into source-controlled files.
    # Optionally the admin UI can call core.models.StripeSettings.set_stripe_key.
    return False