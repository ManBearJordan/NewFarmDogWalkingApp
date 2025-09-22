# 04 — Stripe Billing

## Key Management
- Key is set in **Admin** → stored securely (DB/Keyring). Mode derived by prefix (`sk_test_` vs `sk_live_`).

## Customers
- `ensure_customer(client)` finds/creates by email. Links `stripe_customer_id`. May sync phone/address.

## Invoices — Batch Algorithm
- On **booking creation** (single or multiple):
  1) Read `client.credit_cents`.
  2) For each row, **apply credit first**.
  3) If any `net_due > 0`, create or reuse **one draft invoice** for the batch.
  4) Push line items for each invoiced row.
  5) After the loop, **deduct credit once** (`use_client_credit(total_used)`).
  6) If an invoice exists: **open draft** invoice URL for operator.
- Booking row state:
  - **Fully credit-covered** → `stripe_invoice_id = NULL`.
  - **Invoiced** → `stripe_invoice_id` set to draft/final invoice id.

## Draft vs Finalized Linking
- UI shows “Open Invoice” per booking:
  - Initially links to **draft** invoice if not finalized.
  - When Stripe marks the invoice **finalized** (webhook `invoice.finalized`), update the booking’s link target to the **final invoice** URL.
  - If invoice is **paid**/sent, same URL applies.

## Subscriptions
- Plans/products can represent weekly packs, etc.
- Active subs feed the **materializer** that creates `SubOccurrence` holds and, optionally, auto-create future bookings according to policy.

## Webhooks (critical)
- `invoice.finalized` → update booking invoice link state to finalized.
- `invoice.payment_succeeded/failed` → surface status and optionally email.
- `customer.subscription.updated/deleted` → re-materialize future holds.
