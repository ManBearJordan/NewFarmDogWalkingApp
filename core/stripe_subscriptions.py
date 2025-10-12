from datetime import date, datetime, timedelta, time
from dateutil.rrule import rrule, WEEKLY, MO, TU, WE, TH, FR, SA, SU
from django.utils import timezone
from django.db import transaction
import stripe

from .models import Client, StripeSubscriptionLink, StripeSubscriptionSchedule, SubOccurrence
from .stripe_integration import get_stripe_key
from .service_map import get_service_code

WEEKDAY_MAP = {"mon": MO, "tue": TU, "wed": WE, "thu": TH, "fri": FR, "sat": SA, "sun": SU}

def _tzaware(dt_naive):
    tz = timezone.get_current_timezone()
    return timezone.make_aware(dt_naive, tz)

def resolve_service_code(nickname_or_prod_name):
    """
    Resolve service code from Stripe price nickname or product name.
    Uses the service_map.get_service_code() for fuzzy matching.
    Falls back to 'walk' if no match.
    """
    result = get_service_code(nickname_or_prod_name)
    return result if result else "walk"

def ensure_links_for_client_stripe_subs():
    """
    For all clients with stripe_customer_id, fetch their active Stripe subscriptions
    and ensure a StripeSubscriptionLink exists with a guessed service_code.
    """
    stripe.api_key = get_stripe_key()
    for client in Client.objects.exclude(stripe_customer_id__isnull=True).exclude(stripe_customer_id__exact=""):
        subs = stripe.Subscription.list(customer=client.stripe_customer_id, status="all", expand=["data.items.price.product"])
        for s in subs.auto_paging_iter():
            sub_id = s["id"]
            status = s["status"]
            price = s["items"]["data"][0]["price"]
            product = price.get("product") or {}
            nickname = price.get("nickname") or ""
            prod_name = product.get("name") or ""
            # Resolve to our service_code from nickname/product name (fallback to 'walk')
            service_code = resolve_service_code(nickname or prod_name) or "walk"
            link, _ = StripeSubscriptionLink.objects.update_or_create(
                stripe_subscription_id=sub_id,
                defaults={"client": client, "service_code": service_code, "status": status},
            )
    return True

def _weekdays_from_csv(csv_str):
    items = [i.strip().lower() for i in csv_str.split(",") if i.strip()]
    return [WEEKDAY_MAP[i] for i in items if i in WEEKDAY_MAP]

def materialize_future_holds(sub_link: StripeSubscriptionLink, horizon_days: int = 30):
    """
    For a given subscription link with an existing schedule, create/refresh SubOccurrence
    records for the next `horizon_days`. Uses schedule.weekdays + default_time/duration.
    """
    sched = getattr(sub_link, "schedule", None)
    if not sched:
        return {"created": 0, "skipped": "no-schedule"}
    today = timezone.localdate()
    until = today + timedelta(days=horizon_days)
    wk = _weekdays_from_csv(sched.weekdays_csv)
    if not wk:
        return {"created": 0, "skipped": "empty-weekdays"}

    hh, mm = [int(x) for x in sched.default_time.split(":")]
    dur = timedelta(minutes=sched.default_duration_minutes)
    created = 0

    for dt in rrule(WEEKLY, byweekday=wk, dtstart=datetime.combine(today, time(0,0)), until=datetime.combine(until, time(23,59))):
        start_naive = datetime.combine(dt.date(), time(hh, mm))
        start = _tzaware(start_naive)
        end = start + dur
        # Upsert SubOccurrence for this day
        obj, made = SubOccurrence.objects.get_or_create(
            stripe_subscription_id=sub_link.stripe_subscription_id,
            start_dt=start,
            end_dt=end,
            defaults={"active": True},
        )
        if made:
            created += 1
    sched.last_materialized_until = until
    sched.save(update_fields=["last_materialized_until"])
    return {"created": created}
