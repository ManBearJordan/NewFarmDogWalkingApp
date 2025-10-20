from django.apps import AppConfig
import logging
import os
import sys
from django.conf import settings

log = logging.getLogger(__name__)

class NewfarmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'newfarm'

    def ready(self):
        """
        Start the in-process scheduler exactly once per process.
        We avoid double-start under the Django autoreloader by checking RUN_MAIN.
        Under waitress (prod) the autoreloader is not active, but this guard is safe.
        """
        # Don't spin up background jobs when running mgmt commands
        mgmt_cmds = {
            "migrate", "makemigrations", "collectstatic", "test", "shell",
            "loaddata", "dumpdata", "createsuperuser", "check",
        }
        if any(cmd in sys.argv for cmd in mgmt_cmds):
            return
        if getattr(settings, "DISABLE_SCHEDULER", False):
            return
        
        try:
            run_main = os.environ.get("RUN_MAIN", "true").lower() == "true"
        except Exception:
            run_main = True

        if not run_main:
            return

        try:
            from .scheduler import start_scheduler
            start_scheduler()
        except Exception as exc:
            # Never crash the app if scheduler fails; log and continue serving.
            log.exception("Failed to start scheduler: %s", exc)
