from django.core.management.base import BaseCommand
import logging

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Create/refresh bookings based on Stripe invoices."

    def handle(self, *args, **opts):
        try:
            from core import sync as sync_mod
            if hasattr(sync_mod, "build_bookings_from_invoices"):
                summary = sync_mod.build_bookings_from_invoices()
                self.stdout.write(self.style.SUCCESS(f"Invoice bookings built: {summary}"))
                return
        except ImportError:
            pass  # core.sync module doesn't exist yet
        except Exception as exc:
            log.exception("build_bookings_from_invoices failed in project code: %s", exc)
            raise

        self.stdout.write(self.style.WARNING(
            "No core.sync.build_bookings_from_invoices() found. TODO: implement invoice->booking logic."
        ))
