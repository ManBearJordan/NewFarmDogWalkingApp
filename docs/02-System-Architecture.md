# 02 — System Architecture

## High-Level
- **Backend:** Django + PostgreSQL (or SQLite in dev). REST/JSON (or HTMX) for server-rendered pages.
- **Frontend:** Django templates (Bootstrap) initially. Optional React later.
- **Integrations:**
  - **Stripe** (Billing): customers, invoices, subscriptions, webhooks.
  - **Google Calendar** (optional): token-based push/pull.
  - **ICS** export: downloadable feeds.
- **Auth:** Django auth + optional customer portal auth via magic links.
- **Background jobs:** Django management commands / Celery (optional) for subscription sync and email sends.
- **Environments:** dev / staging / prod.
- **Hosting:** Any VPS/managed host (e.g., Railway, Fly.io, Heroku-style), with HTTPS.

## Modules (Server-Side)
- `core/clients`, `core/pets`, `core/bookings`, `core/subscriptions`, `core/calendar`, `core/reports`, `core/adminpanel`, `core/billing` (Stripe), `core/exports` (ICS), `core/keymgmt` (Stripe key), `core/crm` (tags/notes).

## Data Flow — Booking → Billing
1) Create booking(s).
2) Apply client **credit** first.
3) For **any amount due**, create/reuse **one draft invoice** (batch).
4) When invoice **finalizes** (via dashboard or webhook), booking’s “Open invoice” now points to the **final invoice URL**.
