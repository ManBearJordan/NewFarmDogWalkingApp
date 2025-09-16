"""
Celery configuration for the dog walking Django app.

This file configures Celery for background task processing, including
subscription syncing and booking generation tasks.
"""

import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dogwalking_django.settings')

app = Celery('dogwalking_django')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery beat schedule for periodic tasks
app.conf.beat_schedule = {
    'sync-subscriptions-daily': {
        'task': 'core.tasks.sync_all_subscriptions',
        'schedule': 3600.0,  # Run every hour
    },
    'cleanup-old-bookings': {
        'task': 'core.tasks.cleanup_old_bookings',
        'schedule': 86400.0,  # Run daily
    },
}

app.conf.timezone = settings.TIME_ZONE

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')