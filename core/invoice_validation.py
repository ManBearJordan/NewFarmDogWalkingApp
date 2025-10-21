from datetime import datetime
from zoneinfo import ZoneInfo
from django.utils.timezone import make_naive, is_aware
import logging
from .models import Booking, Service

log = logging.getLogger(__name__)
BRISBANE = ZoneInfo("Australia/Brisbane")

KNOWN_KEYS = {"booking_id", "booking_start", "booking_end", "dogs", "location", "service_code"}


def _parse_iso_local(dt_str: str):
    """Parse ISO datetime string and convert to Brisbane-local naive datetime."""
    if not dt_str:
        return None
    s = dt_str.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None
    if is_aware(dt):
        dt = dt.astimezone(BRISBANE)
        return make_naive(dt, BRISBANE)
    # If already naive, assume it's in Brisbane timezone
    return dt


def _cmp_dt(a, b):
    """
    Compare two datetime objects for equality.
    Handles comparison between aware and naive datetimes by converting both to naive Brisbane time.
    """
    from django.utils.timezone import make_naive, is_aware
    
    # Convert both to naive if needed
    if is_aware(a):
        a = make_naive(a, BRISBANE)
    if is_aware(b):
        b = make_naive(b, BRISBANE)
    
    return a == b


def validate_invoice_against_bookings(invoice_obj):
    """
    For each invoice line with metadata.booking_id:
      - compare booking_start/booking_end/dogs/location/service_code
      - if mismatch: set requires_admin_review with a JSON diff
    Handles multiple line-items and multiple bookings per invoice.
    """
    # stripe object or dict
    invoice_id = getattr(invoice_obj, "id", None) or invoice_obj.get("id")
    if hasattr(invoice_obj, "lines"):
        lines = getattr(invoice_obj.lines, "data", []) or []
    else:
        lines = (invoice_obj.get("lines") or {}).get("data", []) or []

    for li in lines:
        # robust access to metadata
        md = getattr(li, "metadata", None)
        if md is None and isinstance(li, dict):
            md = li.get("metadata")
        if not md:
            continue
        booking_id = md.get("booking_id")
        if not booking_id:
            continue
        try:
            bid = int(str(booking_id))
        except Exception:
            log.warning("Invoice %s: non-integer booking_id=%r", invoice_id, booking_id)
            continue

        b = Booking.objects.filter(id=bid).select_related("service").first()
        if not b:
            log.warning("Invoice %s: booking_id %s not found locally", invoice_id, booking_id)
            continue

        diff = {}
        inv_start = _parse_iso_local(md.get("booking_start"))
        inv_end = _parse_iso_local(md.get("booking_end"))
        if inv_start and not _cmp_dt(b.start_dt, inv_start):
            diff["start_dt"] = {"booking": b.start_dt.isoformat(), "invoice": inv_start.isoformat()}
        if inv_end and not _cmp_dt(b.end_dt, inv_end):
            diff["end_dt"] = {"booking": b.end_dt.isoformat(), "invoice": inv_end.isoformat()}

        if "dogs" in md:
            try:
                inv_dogs = int(md["dogs"])
                if getattr(b, "dogs", None) is not None and b.dogs != inv_dogs:
                    diff["dogs"] = {"booking": b.dogs, "invoice": inv_dogs}
            except Exception:
                log.warning("Invoice %s b%s: invalid dogs=%r", invoice_id, b.id, md["dogs"])

        if "location" in md:
            inv_loc = (md.get("location") or "").strip()
            if (b.location or "") != inv_loc:
                diff["location"] = {"booking": b.location or "", "invoice": inv_loc}

        if "service_code" in md:
            inv_svc = (md.get("service_code") or "").strip()
            if b.service and b.service.code and b.service.code != inv_svc:
                diff["service_code"] = {"booking": b.service.code, "invoice": inv_svc}

        # optional debug: unknown keys present
        unknown = sorted(set(md.keys()) - KNOWN_KEYS)
        if unknown:
            log.debug("Invoice %s b%s: unused metadata keys: %s", invoice_id, b.id, unknown)

        if diff:
            b.requires_admin_review = True
            b.review_diff = diff
            b.review_source_invoice_id = invoice_id
            b.save(update_fields=["requires_admin_review", "review_diff", "review_source_invoice_id"])
            log.warning("Invoice %s: booking %s flagged for review: %s", invoice_id, b.id, diff)

    return True
