"""
Lightweight in-process scheduler for periodic Stripe sync.
Uses APScheduler's BackgroundScheduler so no external services are required.
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.core.management import call_command, get_commands
from django.core.management.base import CommandError

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.triggers.interval import IntervalTrigger
except Exception:  # pragma: no cover
    BackgroundScheduler = None  # type: ignore[assignment]
    DateTrigger = None          # type: ignore[assignment]
    IntervalTrigger = None      # type: ignore[assignment]

log = logging.getLogger(__name__)

_scheduler_started = False
_scheduler_lock = threading.Lock()
_scheduler: BackgroundScheduler | None = None


def _safe_call(cmd_name: str, **kwargs):
    """Call a management command if present; otherwise log and continue."""
    try:
        log.info("Running management command: %s", cmd_name)
        call_command(cmd_name, **kwargs)
    except CommandError as ce:
        # Command not found or bad usage – skip but log
        log.warning("Command '%s' skipped: %s", cmd_name, ce)
    except Exception as exc:  # pragma: no cover
        log.exception("Command '%s' failed: %s", cmd_name, exc)


def _run_sync_job():
    """
    Full sync pipeline. This keeps the instance self-contained:
      1) customers            -> internal Customer table
      2) subscriptions        -> internal Subscription table
      3) bookings generation  -> derive bookings from invoices/subs
    Commands are optional; if a command is missing, we just skip it.
    """
    log.info("Stripe sync job: starting")
    
    # Prefer sync_all if available, as it runs all sync steps in proper order
    if "sync_all" in get_commands():
        _safe_call("sync_all")
    else:
        # Fallback: call individual commands
        # Some repos use these names; we call defensively:
        # - sync_customers / sync_stripe_customers / sync_stripe
        for name in ("sync_customers", "sync_stripe_customers", "sync_stripe"):
            _safe_call(name)
            break
        # Subscriptions
        for name in ("sync_subscriptions",):
            _safe_call(name)
        # Build bookings (from invoices or subs)
        for name in ("build_bookings_from_invoices", "build_bookings"):
            _safe_call(name)
            break
    
    log.info("Stripe sync job: complete")


def start_scheduler():
    """
    Start the in-process scheduler exactly once per process.
    - STARTUP_SYNC=1: run a single sync ~5s after boot
    - PERIODIC_SYNC=1: run every SYNC_INTERVAL_MINUTES (default 15, min 5)
    """
    global _scheduler_started, _scheduler
    if BackgroundScheduler is None:
        log.warning("APScheduler not installed; periodic syncing disabled.")
        return

    with _scheduler_lock:
        if _scheduler_started:
            return

        _scheduler_started = True

        tz = getattr(settings, "TIME_ZONE", "UTC")
        _scheduler = BackgroundScheduler(timezone=tz)
        _scheduler.start(paused=True)

        # One-off startup sync (optional)
        if str(os.environ.get("STARTUP_SYNC", "0")).strip().lower() in ("1", "true"):
            run_at = datetime.now(timezone.utc) + timedelta(seconds=5)
            _scheduler.add_job(
                _run_sync_job,
                trigger=DateTrigger(run_date=run_at),
                id="nfdw-startup-sync",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            log.info("Startup sync scheduled (~5s)")

        # Periodic sync (optional)
        if str(os.environ.get("PERIODIC_SYNC", "0")).strip().lower() in ("1", "true"):
            try:
                minutes = int(os.environ.get("SYNC_INTERVAL_MINUTES", "15"))
            except ValueError:
                minutes = 15
            minutes = max(5, minutes)
            _scheduler.add_job(
                _run_sync_job,
                trigger=IntervalTrigger(minutes=minutes),
                id="nfdw-periodic-sync",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            log.info("Periodic sync scheduled every %s minute(s)", minutes)

        _scheduler.resume()
        log.info("Scheduler started.")


def shutdown_scheduler():
    """Optional: call on graceful shutdown if you wire signals."""
    global _scheduler
    if _scheduler:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None
