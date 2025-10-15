from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
import logging

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run a full Stripe sync: customers -> subscriptions -> build bookings. Skips parts that aren't present."

    def handle(self, *args, **options):
        def _try(cmd):
            try:
                log.info("sync_all: %s", cmd)
                call_command(cmd)
            except CommandError as ce:
                self.stdout.write(self.style.WARNING(f"Skipping '{cmd}': {ce}"))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"'{cmd}' failed: {exc}"))

        for name in ("sync_customers", "sync_stripe_customers", "sync_stripe"):
            _try(name)
            break
        _try("sync_subscriptions")
        for name in ("build_bookings_from_invoices", "build_bookings"):
            _try(name)
            break
        self.stdout.write(self.style.SUCCESS("sync_all finished"))
