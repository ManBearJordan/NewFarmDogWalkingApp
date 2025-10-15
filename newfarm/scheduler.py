"""
Lightweight in-process scheduler for periodic Stripe sync.
Uses APScheduler's BackgroundScheduler so no external services are required.
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import timedelta

from django.conf import settings
from django.core.management import call_command

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
except Exception:  # pragma: no cover
    BackgroundScheduler = None  # type: ignore[assignment]
    IntervalTrigger = None  # type: ignore[assignment]

log = logging.getLogger(__name__)

_scheduler_started = False
_scheduler_lock = threading.Lock()
_scheduler: BackgroundScheduler | None = None


def _run_sync_job():
    """Invoke the existing management command to sync from Stripe."""
    try:
        log.info("Stripe sync job: starting")
        call_command("sync_subscriptions")
        log.info("Stripe sync job: complete")
    except Exception as exc:  # pragma: no cover
        log.exception("Stripe sync job failed: %s", exc)


def start_scheduler():
    """
    Start the in-process scheduler once per process.
    - Honors STARTUP_SYNC=1: run one-time sync ~5s after boot.
    - Honors PERIODIC_SYNC=1: run every SYNC_INTERVAL_MINUTES (default 15).
    """
    global _scheduler_started, _scheduler
    if BackgroundScheduler is None:
        log.warning("APScheduler not installed; periodic syncing disabled.")
        return

    with _scheduler_lock:
        if _scheduler_started:
            return

        _scheduler_started = True
        _scheduler = BackgroundScheduler(timezone=str(getattr(settings, "TIME_ZONE", "UTC")))
        _scheduler.start(paused=True)

        # Startup sync (optional, default off unless env set)
        if str(os.environ.get("STARTUP_SYNC", "0")).strip() in ("1", "true", "True"):
            # run once, shortly after boot
            _scheduler.add_job(
                _run_sync_job,
                trigger=IntervalTrigger(seconds=5),
                id="nfdw-startup-sync",
                max_instances=1,
                replace_existing=True,
                next_run_time=None,  # first tick after interval
            )
            log.info("Startup sync scheduled (in ~5s)")

        # Periodic sync (optional, default off unless env set)
        if str(os.environ.get("PERIODIC_SYNC", "0")).strip() in ("1", "true", "True"):
            try:
                minutes = int(os.environ.get("SYNC_INTERVAL_MINUTES", "15"))
                minutes = max(5, minutes)  # safety floor
            except ValueError:
                minutes = 15
            _scheduler.add_job(
                _run_sync_job,
                trigger=IntervalTrigger(minutes=minutes),
                id="nfdw-periodic-sync",
                max_instances=1,
                replace_existing=True,
            )
            log.info("Periodic sync scheduled every %s minute(s)", minutes)

        _scheduler.resume()
        log.info("Scheduler started.")


def shutdown_scheduler():
    global _scheduler
    if _scheduler:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None
