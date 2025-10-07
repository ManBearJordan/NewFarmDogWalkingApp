# Release checklist

## Before you deploy
- [ ] Pull latest `main`
- [ ] Review CHANGELOG/PRs for migrations (yes: `0007_stripekeyaudit.py`)
- [ ] Verify `.env` in target environment (use `.env.example` as source of truth)

## Deploy steps (Django)
1) Install deps: `pip install -r requirements.txt`
2) Apply migrations: `python manage.py migrate --noinput`
3) Create/update admin user if needed: `python manage.py createsuperuser`
4) Start app (gunicorn/uvicorn/etc.)

## Stripe key
- For desktop/lab: set via **Admin → Stripe Status → Change Stripe Key** (OS keyring if `USE_KEYRING=1`)
- For servers: set `STRIPE_API_KEY` in environment/secrets instead

## Subscription sync
- One-off on boot if `STARTUP_SYNC=1`
- Daily job: run `python manage.py sync_subscriptions` (cron/GitHub Action example in `docs/ops.md`)

## Post-deploy checks
- Stripe Status page renders (non-staff sees mailto link; staff sees change form)
- Portal login works; create test booking; if payment due, hosted invoice link appears
- Calendar shows blue/purple/orange dots, "Troubleshoot Sync" modal returns stats

## Rollback
- Migrations are reversible; if needed: `python manage.py migrate core <previous_migration>`
