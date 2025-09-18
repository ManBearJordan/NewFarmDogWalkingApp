# secrets_config.py
# Configuration file for sensitive keys and secrets
# NOTE: This file contains sensitive information. Do NOT commit it to version control.

import os

# Stripe Secret Key - replace with your actual key
STRIPE_SECRET_KEY = "sk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

def get_stripe_key() -> str:
    """Get Stripe secret key with fallback to environment variables"""
    return STRIPE_SECRET_KEY or os.getenv("STRIPE_API_KEY") or os.getenv("STRIPE_SECRET_KEY") or ""
