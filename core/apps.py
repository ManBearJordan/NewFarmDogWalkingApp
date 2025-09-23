from __future__ import annotations
import os
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
        try:
            if not getattr(settings, "STARTUP_SYNC", False):
                return
            # Avoid double-run with the dev autoreloader
            if os.environ.get("RUN_MAIN") == "true" and self._startup_ran:
                return

            def _do_sync():
                try:
                    from .subscription_sync import sync_subscriptions_to_bookings_and_calendar
                    stats = sync_subscriptions_to_bookings_and_calendar()
                    log.info("Startup subscription sync complete: %s", stats)
                except Exception as e:
                    log.exception("Startup subscription sync failed: %s", e)

            # Nudge a few seconds after boot so migrations/admin are ready
            threading.Timer(3.0, _do_sync).start()
            self._startup_ran = True
        except Exception:
            log.exception("Failed to schedule startup sync")