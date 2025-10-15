from django.core.management.base import BaseCommand
import logging

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sync customers from Stripe into local DB."

    def handle(self, *args, **opts):
        # Call your real sync if present
        try:
            from core import sync as sync_mod  # expected project module
            if hasattr(sync_mod, "sync_customers"):
                summary = sync_mod.sync_customers()
                self.stdout.write(self.style.SUCCESS(f"Customers synced: {summary}"))
                return
        except ImportError:
            pass  # core.sync module doesn't exist yet
        except Exception as exc:
            log.exception("sync_customers failed in project code: %s", exc)
            raise

        # Fallback: present but not implemented in project
        self.stdout.write(self.style.WARNING(
            "No core.sync.sync_customers() found. TODO: implement your customer import logic."
        ))
