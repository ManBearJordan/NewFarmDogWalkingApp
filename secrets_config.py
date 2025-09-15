# secrets_config.py
# Uses your hard-coded Stripe live key so you never have to paste it again.
# NOTE: This is sensitive; don't share this file or commit it to any public repo.

import os

# 🔒 Your live key (as provided by you)
STRIPE_LIVE_SECRET = "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"

def get_stripe_key() -> str:
    # Hard-coded key wins; falls back to env only if you ever clear it here
    return STRIPE_LIVE_SECRET or os.getenv("STRIPE_API_KEY") or os.getenv("STRIPE_SECRET_KEY") or ""
