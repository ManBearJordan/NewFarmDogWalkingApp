from __future__ import annotations
import logging
from typing import Optional, Dict, Any
from django.contrib.auth.models import AnonymousUser
from .models import AdminEvent, Booking

log = logging.getLogger(__name__)

def emit(event_type: str, message: str = "", *, actor=None, booking: Optional[Booking] = None, context: Optional[Dict[str, Any]] = None):
    """
    Persist an AdminEvent and also log it.
    Safe if actor is AnonymousUser/None.
    Keep context small: ids, codes, times.
    """
    try:
        actor_id = None
        if actor and not isinstance(actor, AnonymousUser):
            actor_id = getattr(actor, "id", None)
        ev = AdminEvent.objects.create(
            event_type=event_type,
            message=message or "",
            actor_id=actor_id,
            booking=booking,
            context=context or {},
        )
        log.info("audit %s: %s ctx=%s", event_type, message, (context or {}))
        return ev
    except Exception as e:
        # Never let audit failure block user actions
        log.exception("audit emit failed: %s", e)
        return None
