from django.core.management.base import BaseCommand
from core import stripe_subscriptions
from core.models import StripeSubscriptionLink

class Command(BaseCommand):
    help = "Sync Stripe subscriptions and materialize future holds."
    def handle(self, *args, **kwargs):
        stripe_subscriptions.ensure_links_for_client_stripe_subs()
        for link in StripeSubscriptionLink.objects.all():
            stripe_subscriptions.materialize_future_holds(link, horizon_days=30)
        self.stdout.write(self.style.SUCCESS("Stripe subs synced & holds materialized"))
