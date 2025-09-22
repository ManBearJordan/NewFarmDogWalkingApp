# 11 — API Spec (initial)

## Auth
- Staff: Django auth (session). Customer portal: passwordless email magic links.

## Endpoints (illustrative)
- `POST /api/clients/` create client.
- `POST /api/clients/{id}/credit` add credit_cents.
- `GET /api/services` list_booking_services.
- `POST /api/bookings/batch` create rows (runs billing algorithm).
- `POST /api/sync/subscriptions` run materializer.
- `GET /api/calendar/month?yyyy-mm` dot counts.
- `GET /bookings/export/all.ics` and `GET /bookings/export?ids=...`

## Webhooks
- `POST /webhooks/stripe` handle `invoice.finalized`, `invoice.payment_*`, `customer.subscription.*`.
