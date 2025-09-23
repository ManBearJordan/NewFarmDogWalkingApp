from __future__ import annotations
import threading
from typing import Optional, Dict

from django.conf import settings
from django.utils.timezone import now
import os

_LOCK = threading.RLock()
_MEM: Dict[str, str] = {}  # in-memory override for current process only

def _has_keyring() -> bool:
    if not getattr(settings, "USE_KEYRING", False):
        return False
    try:
        import keyring  # noqa: F401
        return True
    except Exception:
        return False

def _get_from_keyring() -> Optional[str]:
    if not _has_keyring():
        return None
    try:
        import keyring
        return keyring.get_password(settings.KEYRING_SERVICE_NAME, "STRIPE_API_KEY")
    except Exception:
        return None

def _set_in_keyring(value: Optional[str]) -> bool:
    if not _has_keyring():
        return False
    try:
        import keyring
        if value:
            keyring.set_password(settings.KEYRING_SERVICE_NAME, "STRIPE_API_KEY", value)
        else:
            try:
                keyring.delete_password(settings.KEYRING_SERVICE_NAME, "STRIPE_API_KEY")
            except Exception:
                pass
        return True
    except Exception:
        return False

def get_stripe_key() -> Optional[str]:
    """
    Resolve the currently active Stripe secret key.
    Priority: in-memory override → keyring (if enabled) → environment.
    """
    with _LOCK:
        if "STRIPE_API_KEY" in _MEM:
            return _MEM.get("STRIPE_API_KEY") or None
    # keyring
    key = _get_from_keyring()
    if key:
        return key
    # env
    return os.getenv("STRIPE_API_KEY") or None

def update_stripe_key(new_key: Optional[str]) -> None:
    """
    Update key in the most persistent store available:
    - If keyring is enabled → write to keyring and clear in-memory override.
    - Else → set in-memory override for this process (does not write env).
    """
    with _LOCK:
        if _has_keyring():
            _set_in_keyring(new_key)
            # clear memory so keyring is source of truth
            if "STRIPE_API_KEY" in _MEM:
                del _MEM["STRIPE_API_KEY"]
        else:
            # last resort: memory only for this process
            if new_key:
                _MEM["STRIPE_API_KEY"] = new_key
            else:
                _MEM.pop("STRIPE_API_KEY", None)

def get_key_status() -> Dict[str, object]:
    """
    Returns:
      {
        configured: bool,
        mode: 'memory'|'keyring'|'env'|None,
        test_or_live: 'test'|'live'|None,
      }
    """
    key = get_stripe_key()
    mode = None
    with _LOCK:
        if "STRIPE_API_KEY" in _MEM:
            mode = "memory"
    if mode is None:
        if _get_from_keyring():
            mode = "keyring"
        elif os.getenv("STRIPE_API_KEY"):
            mode = "env"
    test_or_live = None
    if key:
        test_or_live = "live" if (key.startswith("sk_live") or "_live_" in key) else "test"
    return {
        "configured": bool(key),
        "mode": mode,
        "test_or_live": test_or_live,
    }