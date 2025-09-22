# 06 — Subscriptions & Calendar

## Subscription Sync (Materializer)
- Command and API: `sync_subscriptions_to_bookings_and_calendar(horizon_days=90)`.
- Steps:
  1) **Clear** future `SubOccurrence` (>= today).
  2) Fetch active Stripe subscriptions.
  3) Compute **future occurrences** within horizon.
  4) **Create** holds (`SubOccurrence.active=1`).
  5) Return stats `{processed, created, cleaned, errors}` and write `subscription_error_log.txt`.

## Calendar (Ops Console)
- Month grid shows dots per day:
  - **Blue** = real Bookings (filtered for status/deleted).
  - **Purple** = SubOccurrence holds.
  - **Orange** = AdminEvent (tasks).
- Clicking a day reveals **bookings only** (no holds) with start/end, client, address, service, pets.

## Auto vs Manual
- Auto sync on app startup and daily job at 03:00 local.
- Manual “Troubleshoot Sync” button runs sync and displays stats.
