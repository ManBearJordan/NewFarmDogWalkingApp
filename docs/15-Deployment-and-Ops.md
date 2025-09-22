# 15 — Deployment & Ops

- Envs: DEV, STAGING, PROD (.env per env).
- `python manage.py sync_subs` daily at 03:00 local via cron.
- Stripe webhook endpoint exposed publicly.
- Backups: daily DB dump; retention 30 days.
- Monitoring: basic uptime + error logging.
