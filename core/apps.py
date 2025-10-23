from __future__ import annotations
import os
import sys
import threading
import logging
from django.apps import AppConfig
from django.conf import settings

log = logging.getLogger(__name__)

class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    _startup_ran = False

    def ready(self):
        """
        Optionally kick off a one-time, background subscription sync shortly after
        server boot. Guarded by env STARTUP_SYNC=1 and avoids duplicate runs under
        Django autoreload by checking RUN_MAIN.
        """
        # First, handle the existing startup sync logic (optional, controlled by STARTUP_SYNC env var)
        try:
            # Don't spin up background jobs when running mgmt commands
            mgmt_cmds = {
                "migrate", "makemigrations", "collectstatic", "test", "shell",
                "loaddata", "dumpdata", "createsuperuser", "check",
            }
            if len(sys.argv) > 1 and sys.argv[1] in mgmt_cmds:
                # Early return only from this try block, not the whole method
                pass
            elif getattr(settings, "DISABLE_SCHEDULER", False):
                # Skip startup sync if scheduler is disabled
                pass
            elif getattr(settings, "STARTUP_SYNC", False):
                # Avoid double-run with the dev autoreloader
                if not (os.environ.get("RUN_MAIN") == "true" and self._startup_ran):
                    def _do_sync():
                        try:
                            from .subscription_sync import sync_subscriptions_to_bookings_and_calendar
                            stats = sync_subscriptions_to_bookings_and_calendar()
                            log.info("Startup subscription sync complete: %s", stats)
                        except Exception as e:
                            log.exception("Startup subscription sync failed: %s", e)
                        
                        # NEW: discover Stripe subs (Stripe-owned) and create/update links
                        try:
                            from . import stripe_subscriptions
                            stripe_subscriptions.ensure_links_for_client_stripe_subs()
                            log.info("Stripe subscription links synced")
                            # For links that already have a schedule, materialize next 30 days
                            from .models import StripeSubscriptionLink
                            for link in StripeSubscriptionLink.objects.all():
                                try:
                                    stripe_subscriptions.materialize_future_holds(link, horizon_days=30)
                                except Exception:
                                    pass
                        except Exception as e:
                            log.exception("Stripe subscription sync failed: %s", e)

                    # Nudge a few seconds after boot so migrations/admin are ready
                    threading.Timer(3.0, _do_sync).start()
                    self._startup_ran = True
        except Exception:
            log.exception("Failed to schedule startup sync")
        
        # Start the background scheduler only when enabled and appropriate.
        # This runs independently of the STARTUP_SYNC logic above.
        try:
            from . import scheduler  # local import so migrations/collectstatic don't break
        except Exception as e:
            log.warning("core.apps: scheduler module not available: %s", e)
            return
        try:
            scheduler.start_scheduler_if_enabled()
        except Exception as e:
            log.exception("core.apps: failed to start scheduler: %s", e)
        
        # Import signals to register them
        import core.signals  # noqa