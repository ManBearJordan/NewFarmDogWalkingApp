# 12 — UI Spec

## Ops Console Tabs (Web)
1) **Clients**: table + actions (credit, Stripe link/open).
2) **Pets**: filter by client, add pet.
3) **Bookings**: range filter presets; multi-row creator; context menu → Open invoice / Delete; Export .ics.
4) **Calendar**: month grid with colored dots; day detail table (bookings only); Troubleshoot Sync.
5) **Subscriptions**: info on auto-sync + delete subscription (admin-only).
6) **Reports**: recent invoices listing.
7) **Admin**: Stripe key; Google connect; admin events; DB backup.

## Customer-Facing (Website)
- Public booking widget:
  - Pick service, date/time, dog count, address, notes.
  - If email matches existing client, pre-fill; else create new client.
  - Payment:
    - If subscription credit or pre-paid pack: net due may be zero.
    - Otherwise, create **Stripe Checkout** or **Payment Link**; booking stays pending until payment succeeds.
- Customer Portal:
  - See past/future bookings, invoices, subscription status, update card, cancel/reschedule within policy.
