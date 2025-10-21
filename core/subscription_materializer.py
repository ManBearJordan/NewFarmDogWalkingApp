from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from .models import StripeSubscriptionSchedule, Service, Booking
import logging

log = logging.getLogger(__name__)

HORIZON_WEEKS = 8  # materialize ~2 months ahead


def _next_week_start(dt):
    """Get the Monday of the week containing dt."""
    return dt - timedelta(days=dt.weekday())


def _ensure_tz(dt):
    """Keep naive as-is if the app is naive; if aware, attach timezone."""
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


@transaction.atomic
def materialize_future_holds(now_dt=None):
    """
    Create future bookings based on StripeSubscriptionSchedule:
    - repeats: weekly or fortnightly
    - days: comma list of weekdays (MON..SUN)
    - start_time: HH:MM
    - service_code: must resolve to active service with duration
    Fallback: WED 10:30, location 'Home'
    """
    now_dt = now_dt or timezone.localtime()
    week0 = _next_week_start(now_dt)
    created = 0

    for sched in StripeSubscriptionSchedule.objects.select_related('sub__client').filter(sub__active=True):
        # Enforce completeness before creating any bookings
        if not sched.is_complete():
            log.info("Skipping sched %s (%s): incomplete (%s)", sched.id, sched.sub.stripe_subscription_id, ",".join(sched.missing_fields()))
            continue
        
        # Get service from the link's service_code
        service_code = sched.sub.service_code
        service = None
        if service_code:
            service = Service.objects.filter(code=service_code, is_active=True).first()
        
        if not service or not service.duration_minutes:
            log.info("Skipping sched %s: missing/invalid service or duration", sched.id)
            continue

        interval = sched.interval_weeks()  # 1=weekly, 2=fortnightly
        days = sched.parsed_days()
        t = sched.parsed_time()
        location = sched.location or "Home"

        for wk in range(0, HORIZON_WEEKS, interval):
            week_start = week0 + timedelta(weeks=wk)
            for d in days:
                day_dt = week_start + timedelta(days=d)  # d: 0=Mon
                start_dt = datetime(
                    year=day_dt.year,
                    month=day_dt.month,
                    day=day_dt.day,
                    hour=t.hour, 
                    minute=t.minute,
                )
                start_dt = _ensure_tz(start_dt)
                end_dt = start_dt + timedelta(minutes=service.duration_minutes)
                
                # Idempotency: don't duplicate an existing booking for same client+service+start
                exists = Booking.objects.filter(
                    client=sched.sub.client,
                    service=service,
                    start_dt=start_dt,
                ).exists()
                if exists:
                    continue
                
                Booking.objects.create(
                    client=sched.sub.client,
                    service=service,
                    service_code=service_code,
                    service_name=service.name,
                    service_label=service.name,
                    start_dt=start_dt,
                    end_dt=end_dt,
                    price_cents=0,
                    status="pending",
                    location=location,
                )
                created += 1
                
    log.info("Materialization done: created=%s", created)
    return {"created": created}
