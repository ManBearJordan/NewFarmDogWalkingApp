# 14 — Acceptance Tests

## A. Credit + Invoice Reuse
- Client has 6000 credit_cents. Create 3 bookings at 3500 each in **one batch**.
- Expected:
  - Two fully covered (stripe_invoice_id NULL).
  - Third partially invoiced.
  - Exactly **1** draft invoice created/reused; URL returned.

## B. Overnight Handling
- Booking with “Overnight …” service → `end_dt = start_dt + 1 day`.

## C. Open Invoice Behavior
- Immediately after create (amount due) → **draft** invoice URL opens.
- After webhook `invoice.finalized` → booking now opens **finalized** invoice URL.

## D. Calendar Markers
- Blue bookings, purple holds, orange admin events; day click shows bookings only.

## E. Stripe Mode Awareness
- Test key opens test dashboard; live key opens live dashboard.

## F. Website Booking
- Customer completes booking+payment via website → appears in ops console calendar; invoice linked; status paid.
