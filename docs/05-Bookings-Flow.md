# 05 — Bookings Flow

## Creating Bookings (Back Office)
- Form supports **multi-row**: Date / Start / End (30-min steps), Service, Location, Dogs, Price (cents), Notes.
- **Overnight rule**: service label/code containing "overnight" auto sets `end_dt = start_dt + 1 day`.
- On submit, run **Batch Algorithm** (see Stripe Billing).

### After Create — What Opens
- If **any amount due**: open **draft** invoice in Stripe for payment/adjustment.
- If **fully credit-covered**: show success with no invoice.
- Each booking row stores `stripe_invoice_id or NULL`.

### Later — When Invoice is Final
- A background webhook updates booking’s invoice status:
  - “Open invoice” now goes to the **finalized** invoice URL.

## Editing/Deleting
- Editing time/price updates line items if invoice is still draft; otherwise requires a **new adjustment** invoice.
- Deleting an invoiced booking requires cancelling invoice item or issuing credit note (operator-confirmed).

## Export
- Export **all** or **selected** bookings to `.ics` (AEST), one VEVENT per booking.
