# TASKS.md

## Phase 1 — Make the current Django app do the core job
- [ ] T1: Create `.env.example` (DJANGO_SECRET_KEY, STRIPE_SECRET_KEY, PORT=8000)
- [ ] T2: Add models: `Booking`, `InvoiceMap`, `SubscriptionMap`, `DedupEvent`, `Rule`
- [ ] T3: Write **Rule engine** (pure function) and unit tests
- [ ] T4: Expand `core/stripe_integration.py` to pull Customers, Subscriptions, Invoices, Items
- [ ] T5: Implement `sync_subs` command: fetch latest → upsert *Map tables* → write `DedupEvent`
- [ ] T6: Implement **allocation service**: map subscriptions/invoices → bookings (uses rules)
- [ ] T7: Build **admin/list screens** for Bookings/Clients; add filters & search
- [ ] T8: Build **calendar feeds**: `/calendar/all.ics` and `/calendar/client/<id>.ics`
- [ ] T9: Add **webhook endpoint** `/stripe/webhook` (idempotent) + tests

## Phase 2 — Desktop wrapper & packaging
- [ ] T10: Add `desktop/` with PyWebview app (`desktop/main.py`) that spawns Django server and opens window
- [ ] T11: PyInstaller spec to bundle app + templates + static
- [ ] T12: Provide a `run` script (PowerShell) to do `dev|test|format` with one command

## Phase 3 — Customer self-service (local web)
- [ ] T13: Public routes to view availability and create bookings (guard rails: quotas, conflicts)
- [ ] T14: Optional auth for customers (token links or simple login)
- [ ] T15: Payment linking: show which bookings come from which Stripe subscription

## Phase 4 — Reliability
- [ ] T16: Nightly sync via Windows Task Scheduler → `python manage.py sync_subs`
- [ ] T17: Reporting pages: “Unmapped invoices”, “Duplicate candidates”, “Failed webhooks”
- [ ] T18: Add basic telemetry (counts, durations) to logs

**Note to AI:** For each task, propose exact files to add/edit, then submit a minimal diff + tests.
