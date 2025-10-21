from __future__ import annotations
import os
import sys
import atexit
import logging
from typing import Optional
from zoneinfo import ZoneInfo

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except Exception:  # pragma: no cover
    BackgroundScheduler = None  # graceful if APScheduler not installed

log = logging.getLogger(__name__)
BRISBANE = ZoneInfo("Australia/Brisbane")

_SCHEDULER: Optional["BackgroundScheduler"] = None
_STARTED = False

def _env_enabled() -> bool:
    """
    Scheduler is opt-in: set an env var to enable (kept generic to avoid leaking env policy here).
    """
    return os.environ.get("NFDW_SCHEDULER", "0") == "1"

def _is_management_command_process() -> bool:
    """
    Avoid starting the scheduler during management commands (migrate, collectstatic, etc.).
    """
    argv = sys.argv[:]
    if not argv:
        return False
    # Heuristic: manage.py present or common cmds present
    cmds = {"migrate", "makemigrations", "collectstatic", "shell", "test", "loaddata", "dumpdata", "createsuperuser"}
    return any(c in argv for c in cmds)

def _get_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except Exception:
        return default

# ----- JOB IMPLEMENTATIONS (safe imports inside) -----
def job_sync_invoices():
    try:
        from .stripe_invoices_sync import sync_invoices
        lookback = _get_int("NFDW_SYNC_INVOICES_LOOKBACK_DAYS", 90)
        res = sync_invoices(days=lookback)
        log.info("scheduler: sync_invoices -> %s", res)
    except Exception as e:
        log.exception("scheduler: sync_invoices failed: %s", e)

def job_materialize():
    try:
        from .subscription_materializer import materialize_all
        weeks = _get_int("NFDW_MATERIALIZE_WEEKS", 12)
        res = materialize_all(horizon_weeks=weeks)
        log.info("scheduler: materialize_all -> %s", res)
    except Exception as e:
        log.exception("scheduler: materialize_all failed: %s", e)

def job_sync_subscription_links():
    """
    Refresh/ensure local links to Stripe subscriptions (no-ops if code/module absent).
    """
    try:
        # If your project exposes a bulk sync, call it here.
        # Fallback: try a function used elsewhere in the app.
        try:
            from .stripe_subscriptions import ensure_links_for_client_stripe_subs as ensure_links  # type: ignore
        except Exception:
            ensure_links = None
        if ensure_links is None:
            log.info("scheduler: no subscription link sync function available; skipping")
            return
        ensure_links()
        log.info("scheduler: sync_subscription_links -> ok")
    except Exception as e:
        log.exception("scheduler: sync_subscription_links failed: %s", e)

# ----- REGISTRATION -----
def _register_jobs(sched: "BackgroundScheduler"):
    """
    Register periodic jobs. Coalesce + single instance prevents overlap.
    Intervals default to sensible values; can be tuned via env.
    """
    inv_mins = _get_int("NFDW_SYNC_INVOICES_MINUTES", 15)
    sub_mins = _get_int("NFDW_SYNC_SUBS_MINUTES", 60)
    mat_mins = _get_int("NFDW_MATERIALIZE_MINUTES", 60)

    sched.add_job(
        job_sync_invoices,
        "interval",
        minutes=inv_mins,
        id="sync_invoices",
        coalesce=True,
        max_instances=1,
        replace_existing=True,
    )
    sched.add_job(
        job_sync_subscription_links,
        "interval",
        minutes=sub_mins,
        id="sync_subscription_links",
        coalesce=True,
        max_instances=1,
        replace_existing=True,
    )
    sched.add_job(
        job_materialize,
        "interval",
        minutes=mat_mins,
        id="materialize_all",
        coalesce=True,
        max_instances=1,
        replace_existing=True,
    )

def start_scheduler_if_enabled():
    """
    Start the background scheduler once per process when enabled and appropriate.
    Safe if called multiple times; later calls are ignored.
    """
    global _SCHEDULER, _STARTED
    if _STARTED:
        return _SCHEDULER
    if not _env_enabled():
        log.info("scheduler: disabled (env switch off)")
        return None
    if _is_management_command_process():
        log.info("scheduler: disabled in management command process")
        return None
    if BackgroundScheduler is None:
        log.warning("scheduler: APScheduler not installed; skipping")
        return None

    try:
        sched = BackgroundScheduler(timezone=BRISBANE)
        _register_jobs(sched)
        sched.start()
        _SCHEDULER = sched
        _STARTED = True
        log.info("scheduler: started with timezone=%s", BRISBANE)
    except Exception as e:
        log.exception("scheduler: failed to start: %s", e)
        _SCHEDULER = None
        _STARTED = False
        return None

    # Clean shutdown on interpreter exit
    def _shutdown():
        global _SCHEDULER, _STARTED
        try:
            if _SCHEDULER:
                _SCHEDULER.shutdown(wait=False)
                log.info("scheduler: shut down")
        except Exception:
            pass
        finally:
            _SCHEDULER = None
            _STARTED = False
    atexit.register(_shutdown)
    return _SCHEDULER
