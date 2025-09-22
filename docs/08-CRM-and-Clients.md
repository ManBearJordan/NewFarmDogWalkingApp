# 08 — CRM & Clients

## Clients
- CRUD with fields: name, email, phone, address, notes, status, credit.
- Stripe actions:
  - **Sync Stripe customers** (link by email or explicit `cus_…`).
  - **Open in Stripe** (customer dashboard).

## Client Credit
- Add credit (in cents); displayed as `$X.XX`.
- Used automatically during booking creation **before** invoicing.

## Tags (optional)
- `CRMManager.get_client_tags(client_id)`; UI shows first 3 tags, then `(+N more)`.
