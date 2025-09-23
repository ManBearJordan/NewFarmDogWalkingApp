# Operations: Subscription Sync

## One-off on server startup
Set `STARTUP_SYNC=1` (in `.env`) and the app will run a background sync a few seconds after boot.
This is implemented in `core.apps.CoreConfig.ready()` and guarded to avoid double runs with Django's
autoreloader.

## Manual run (cron, GitHub Actions, etc.)
```
python manage.py sync_subscriptions
```
This calls `subscription_sync.sync_subscriptions_to_bookings_and_calendar()` and prints stats.

### Example crontab (daily at 02:15 local)
```
15 2 * * * source /path/to/venv/bin/activate && cd /path/to/app && ./manage.py sync_subscriptions >> var/log/sync.log 2>&1
```

## Celery (optional)
If you prefer a worker/beat:
1) Set `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` and `START_CELERY_BEAT=1` in `.env`.
2) Run:
```
celery -A newfarm.celery worker -l info
celery -A newfarm.celery beat -l info
```
Beat will run `core.tasks.daily_subscription_sync` daily at **02:15** (AEST/AEDT).

> The sync is idempotent: it clears & rebuilds **future** holds and re-materializes occurrences.