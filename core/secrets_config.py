import os
import logging

log = logging.getLogger(__name__)

STRIPE_SECRET_KEY = None  # do not hard-code keys here

def get_stripe_key(*, production: bool | None = None) -> str:
    """
    Get Stripe secret key from environment variables.
    In PRODUCTION: raise if missing so we don't silently run with fake data.
    In non-production: return empty string if unset (caller may fallback to sample data).
    """
    key = os.getenv("STRIPE_SECRET_KEY") or os.getenv("STRIPE_API_KEY") or ""
    if production is None:
        production = bool(int(os.getenv("PRODUCTION", "0")))
    if not key:
        msg = "Stripe API key is not set (STRIPE_SECRET_KEY/STRIPE_API_KEY)."
        if production:
            raise RuntimeError(msg + " Set it in .env for production.")
        else:
            log.warning(msg + " Proceeding without Stripe in non-production.")
    return key
