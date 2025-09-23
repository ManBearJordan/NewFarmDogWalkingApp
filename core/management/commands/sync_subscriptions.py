from __future__ import annotations
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Materialize Stripe subscription occurrences and refresh holds (future horizon)."

    def handle(self, *args, **options):
        from core.subscription_sync import sync_subscriptions_to_bookings_and_calendar
        stats = sync_subscriptions_to_bookings_and_calendar()
        self.stdout.write(self.style.SUCCESS(f"Subscription sync complete: {stats}"))