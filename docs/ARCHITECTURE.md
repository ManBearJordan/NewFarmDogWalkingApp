# ARCHITECTURE.md

This project is a **desktop app + local web server** that syncs Stripe data and turns **invoices/subscriptions** into **bookings & calendar entries** with robust deduplication. It also serves a small web UI (future mobile app will talk to the same local server).

## 1) Stack (current and intended)
- **Runtime:** Python 3.x
- **Framework:** Django 4.2 (project: `newfarm`, app: `core`)
- **DB:** SQLite (file in repo root)
- **Payments:** Stripe (API + webhooks)
- **Desktop shell:** PyWebview (native window) showing the local web UI
- **Packaging:** PyInstaller (single-folder exe)
- **CLI/automation:** Django management commands
- **Tests:** pytest + Django test runner

## 2) Repository layout (actual + planned)
- `/manage.py` — Django entry
- `/newfarm/` — Django project (`settings.py`, `urls.py`)
- `/core/` — main app (Stripe helpers, admin, views, templates, management commands)
- `/core/templates/` — server-rendered HTML
- `/core/management/commands/` — e.g. `sync_subs.py`
- `/docs/` — project docs for humans + AI  
  - `ARCHITECTURE.md` (this file)  
  - `CODING_STANDARDS.md`  
  - `TASKS.md` (running checklist the AI updates)
- `/config/` — `.env.example` (no secrets), packaging spec
- `/desktop/` — desktop wrapper (PyWebview app entry)
- `/tests/` — unit/integration tests mirroring `/core/`
- `/scripts/` — dev helpers (`run_dev.ps1`, `seed.ps1`, etc.)
- `run` — single entry script to start dev server / tests / formatters

## 3) Core flows

### A) Stripe → Bookings pipeline
1. **Sync** Stripe objects (Customers, Subscriptions, Invoices, InvoiceItems, Products, Prices).
2. **Deduplicate** by **(stripe_id, object type)** and guard against re-processing with an idempotency table.
3. **Map** subscriptions/invoices → internal **Bookings** (rule-driven):
   - Example: a “Weekly Walk (1h)” price maps to 1 booking per week for N weeks.
4. **Persist** bookings in SQLite; track provenance back to Stripe IDs for traceability.
5. **Calendar**: write iCalendar (.ics) exports and/or create a `/calendar` feed.

### B) Web & Desktop
- **Local web UI** (Django): admin + staff screens for bookings, customers, reports.
- **Desktop wrapper**: PyWebview hosts a native window that points to `http://127.0.0.1:<port>`.
- **Future mobile app**: talks to the same HTTP API (read-only or authenticated write).

## 4) Data model (initial)
- `Client(id, name, email, phone, stripe_customer_id, …)`
- `SubscriptionMap(id, stripe_subscription_id, client_id, plan_code, start, end, status, …)`
- `InvoiceMap(id, stripe_invoice_id, client_id, total, paid, period_start, period_end, …)`
- `Booking(id, client_id, start_dt, end_dt, service_code, source_kind[subscription|invoice|manual], source_id, status, …)`
- `DedupEvent(id, external_id, kind, processed_at, hash)`  ← prevents double-processing
- `Rule(id, service_code, matcher_json, allocation_json, active)` ← JSON rules to turn Stripe items into bookings

## 5) Configuration & secrets
- `.env` (local) provides `STRIPE_SECRET_KEY`, `DJANGO_SECRET_KEY`, `PORT`, etc.
- Never commit real secrets. Webhooks: configurable secret via env.
- All adapters (`core/stripe_integration.py`, etc.) read from env.

## 6) Error handling & logging
- Validate inputs at boundary (webhook, CLI sync).
- Idempotent processing: re-running sync or replaying a webhook must not duplicate bookings.
- Structured logs; one log at the top-level per request/command.

## 7) Testing strategy
- **Unit**: mapping rules, dedup logic, calendar generation.
- **Integration**: fake Stripe payload → pipeline → bookings created (and not duplicated).
- Tests live in `/tests/` mirroring `/core/`.

## 8) Desktop packaging
- PyWebview app (`desktop/main.py`) starts Django dev server (or gunicorn) on a local port, waits until ready, then opens the window.
- PyInstaller bundle excludes dev deps, includes templates/static.

## 9) CI (GitHub Actions)
- On PR: install deps, run format/lint, run tests.
- Build artifacts (optional): produce a Windows exe on tag.

## 10) AI workflow rules (important)
- Before editing many files, the AI must add a short step plan to `/docs/TASKS.md`.
- Keep PRs small (1–5 files). Always update tests/docs with code.
- Prefer adding small modules over inflating one giant file.
