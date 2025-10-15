from django.core.management.base import BaseCommand
import logging

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Create/refresh bookings based on active Stripe subscriptions."

    def handle(self, *args, **opts):
        try:
            from core import sync as sync_mod
            if hasattr(sync_mod, "build_bookings_from_subscriptions"):
                summary = sync_mod.build_bookings_from_subscriptions()
                self.stdout.write(self.style.SUCCESS(f"Subscription bookings built: {summary}"))
                return
        except ImportError:
            pass  # core.sync module doesn't exist yet
        except Exception as exc:
            log.exception("build_bookings_from_subscriptions failed in project code: %s", exc)
            raise

        self.stdout.write(self.style.WARNING(
            "No core.sync.build_bookings_from_subscriptions() found. TODO: implement subscription->booking logic."
        ))
