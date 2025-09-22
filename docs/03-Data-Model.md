# 03 — Data Model

Persist **money in cents**. All times timezone-aware for **Australia/Brisbane**.

## Tables/Models
### Client
- `id, name, email, phone, address, notes`
- `credit_cents:int=0`
- `status:enum('active','inactive','archived')`
- `stripe_customer_id`

### Pet
- `id, client_id→Client`
- `name (required)`, `species='dog'`, `breed`, `meds`, `behaviour`

### Booking
- `id, client_id→Client`
- `service_code, service_name, service_label`
- `start_dt, end_dt` (overnight rule may +1 day)
- `location, dogs:int=1, notes`
- `status:enum('scheduled','completed','cancelled','voided')`
- `price_cents:int`
- `stripe_invoice_id (nullable)`
- `deleted:bool=false`

### BookingPet
- `booking_id→Booking, pet_id→Pet`

### SubOccurrence (calendar holds)
- `id, stripe_subscription_id, start_dt, end_dt, active:bool`

### AdminEvent
- `id, due_dt, title, notes`

### StripeSettings (key mgmt)
- `id=1, secret_key_encrypted, mode ('test'|'live') (derived)`, timestamps

## Derived Rules
- Filter “visible bookings” to exclude deleted or cancelled/void variants.
- Service label fallback priority: `service_label → service_name → service_code → product_name → price_nickname → "Service"`.
