from __future__ import annotations
from celery import shared_task

@shared_task(name="core.tasks.daily_subscription_sync")
def daily_subscription_sync() -> dict:
    """
    Daily refresh of subscription occurrences → holds → bookings/calendar.
    Safe to run multiple times; should be idempotent.
    """
    from .subscription_sync import sync_subscriptions_to_bookings_and_calendar
    return sync_subscriptions_to_bookings_and_calendar()