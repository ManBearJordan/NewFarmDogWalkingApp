"""
User-ready Stripe key manager.

Behavior:
- Primary: read STRIPE_SECRET_KEY env var at runtime.
- Persist once (user-first-run) into OS keyring if keyring is available.
- Admin UI calls update_stripe_key() to replace the stored key.
"""
import os
import sys
from typing import Optional, Dict

SERVICE_NAME = "NewFarmDogWalkingApp"
KEY_NAME = "stripe_secret_key"

KEYRING_AVAILABLE = False
try:
    import keyring  # type: ignore
    KEYRING_AVAILABLE = True
except Exception:
    KEYRING_AVAILABLE = False

def get_stripe_key() -> str:
    # env override
    for name in ("STRIPE_SECRET_KEY", "STRIPE_API_KEY"):
        v = os.getenv(name)
        if v:
            return v.strip()
    # keyring
    if KEYRING_AVAILABLE:
        try:
            v = keyring.get_password(SERVICE_NAME, KEY_NAME)
            if v:
                return v.strip()
        except Exception:
            pass
    # django model fallback
    try:
        from core.models import StripeSettings
        k = StripeSettings.get_stripe_key()
        if k:
            return k
    except Exception:
        pass
    return ""

def set_stripe_key(key: str) -> bool:
    if not key or not isinstance(key, str):
        return False
    k = key.strip()
    if len(k) < 10:
        return False
    success = False
    if KEYRING_AVAILABLE:
        try:
            keyring.set_password(SERVICE_NAME, KEY_NAME, k)
            success = True
        except Exception:
            pass
    try:
        from core.models import StripeSettings
        if StripeSettings.set_stripe_key(k):
            success = True
    except Exception:
        pass
    # as last resort on Windows, persist env via setx (best-effort; less secure)
    if not success and sys.platform.startswith("win"):
        try:
            import subprocess
            subprocess.run(["setx", "STRIPE_SECRET_KEY", k], check=True)
            success = True
        except Exception:
            pass
    return bool(success)

def delete_stripe_key() -> bool:
    deleted = False
    if KEYRING_AVAILABLE:
        try:
            keyring.delete_password(SERVICE_NAME, KEY_NAME)
            deleted = True
        except Exception:
            pass
    try:
        from core.models import StripeSettings
        StripeSettings.set_stripe_key("")
        deleted = True
    except Exception:
        pass
    return deleted

def prompt_for_stripe_key() -> Optional[str]:
    try:
        v = input("Enter your Stripe secret key (or press Enter to skip): ").strip()
    except Exception:
        return None
    return v or None

def update_stripe_key(parent=None) -> bool:
    """
    GUI/app admin entrypoint. If GUI present, app should call this and pass parent QWidget.
    For packaging, the GUI will present a password input. Here we fallback to prompt_for_stripe_key.
    """
    k = prompt_for_stripe_key()
    if k:
        return set_stripe_key(k)
    return False

def get_key_status() -> Dict[str, Optional[object]]:
    env = None
    for name in ("STRIPE_SECRET_KEY", "STRIPE_API_KEY"):
        v = os.getenv(name)
        if v:
            env = v
            break
    kr = None
    if KEYRING_AVAILABLE:
        try:
            kr = keyring.get_password(SERVICE_NAME, KEY_NAME)
        except Exception:
            pass
    dj = None
    try:
        from core.models import StripeSettings
        dj = StripeSettings.get_stripe_key()
    except Exception:
        pass
    storage = None
    val = None
    if env:
        storage = "env"; val = env
    elif kr:
        storage = "keyring"; val = kr
    elif dj:
        storage = "django"; val = dj
    key_type = None
    if val:
        if val.startswith("sk_test"): key_type = "test"
        elif val.startswith("sk_live"): key_type = "live"
    return {
        "key_stored": bool(val),
        "key_type": key_type,
        "service_name": SERVICE_NAME,
        "key_name": KEY_NAME,
        "keyring_available": KEYRING_AVAILABLE,
        "storage_method": storage,
    }