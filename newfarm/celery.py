from __future__ import annotations
import os
from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "newfarm.settings")
app = Celery("newfarm")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

@app.on_after_configure.connect
def _announce(sender, **kwargs):
    sender.log.info("Celery configured. Timezone=%s Broker=%s", settings.TIME_ZONE, settings.CELERY_BROKER_URL)

@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")