# Portal Pre-pay & Flexible Capacity System

This document describes the new portal pre-pay booking flow with flexible daily capacity management.

## Features

### 1. Flexible Daily Timetable
- Define arbitrary time blocks for each day (e.g., "Morning Run 7:00-10:30", "Midday 11:00-14:00")
- No fixed windows - complete flexibility in scheduling
- "Copy yesterday" button for easy setup

### 2. Per-Service Capacity Management
- Set capacity limits per service within each time block
- Track available slots in real-time
- Prevent overbooking with short-lived holds during checkout

### 3. Client Login Controls
- **Disable portal login**: Deactivate a client's login without removing the account
- **Remove portal login**: Unlink a client from their user account
- **Can self-reschedule**: Per-client flag to enable/disable rescheduling permissions

### 4. Pre-pay Portal Flow
- Clients see real-time capacity for available time blocks
- Payment happens BEFORE booking is created
- Uses Stripe PaymentIntents (no invoice created for portal bookings)
- Capacity holds prevent race conditions during checkout

## Models

### ServiceDefaults
Stores default duration for each service type:
```python
ServiceDefaults.objects.create(
    service_code="walk",
    duration_minutes=60,
    notes="Standard walk"
)
```

### TimetableBlock
Defines time blocks for a specific date:
```python
TimetableBlock.objects.create(
    date=date(2025, 10, 8),
    start_time=time(9, 0),
    end_time=time(12, 0),
    label="Morning Run"
)
```

### BlockCapacity
Sets capacity per service within a block:
```python
BlockCapacity.objects.create(
    block=morning_block,
    service_code="walk",
    capacity=5,
    allow_overlap=False
)
```

### CapacityHold
Short-lived holds (10 minutes) during payment processing:
```python
hold = create_hold(block, "walk", client)
# Automatically expires after 10 minutes
```

## Admin Interface

### Capacity Editor
Access at: `/admin/capacity/?date=YYYY-MM-DD`

Features:
- Add time blocks with start/end times and labels
- Set per-service capacities for each block
- Copy yesterday's configuration
- View current capacity settings

### Client Admin Actions
In Django Admin > Clients, select clients and use:
- **Disable portal login**: Sets user.is_active = False
- **Remove portal login**: Unlinks client.user (optionally deletes user)

### Client Fields
- `can_self_reschedule`: Boolean flag visible in admin list and edit forms
- `user`: OneToOne link to auth.User (for portal access)

## Portal Endpoints

### Standard Portal Booking (existing)
- `/portal/bookings/new/` - Traditional booking form
- Uses credit-first billing, creates invoice if needed

### New Pre-pay Portal Booking
- `/portal/bookings/new-prepay/` - New pre-pay booking form
- `/portal/blocks/?date=YYYY-MM-DD&service_code=walk` - Get available blocks (AJAX)
- `/portal/checkout/start/` - Create PaymentIntent and hold
- `/portal/checkout/finalize/` - Confirm payment and create booking

## Usage Example

### 1. Set up service defaults (one-time)
```python
ServiceDefaults.objects.create(service_code="walk", duration_minutes=60)
ServiceDefaults.objects.create(service_code="daycare", duration_minutes=480)
```

### 2. Define daily timetable
Access `/admin/capacity/?date=2025-10-08` and:
1. Add block: 09:00-12:00 "Morning Run"
2. Set capacity: walk=5
3. Add block: 13:00-16:00 "Afternoon"
4. Set capacity: walk=3, daycare=2

### 3. Client books through portal
1. Client navigates to `/portal/bookings/new-prepay/`
2. Selects service, date, and time block
3. Sees available capacity in real-time
4. Enters payment details (Stripe.js integration)
5. On successful payment, booking is created

### 4. Capacity tracking
- Bookings count against block capacity
- Active holds (during payment) also count
- Expired holds are automatically purged
- Admin can see remaining capacity at any time

## Integration Notes

### Stripe.js Integration
The template `/core/templates/core/portal_booking_form_prepay.html` includes:
- Placeholder for Stripe.js PaymentIntent confirmation
- TODO comments where to add Stripe publishable key and card element
- Backend endpoints ready to receive confirmation

Current flow:
1. `/portal/checkout/start/` creates PaymentIntent and returns client_secret
2. Client-side Stripe.js confirms payment (TODO: implement)
3. `/portal/checkout/finalize/` creates booking after payment confirmation

### Database Schema
All migrations are in `core/migrations/0008_servicedefaults_booking_block_label_and_more.py`

New fields:
- `Client.can_self_reschedule` (BooleanField)
- `Booking.block_label` (CharField, nullable)

New models:
- `ServiceDefaults`
- `TimetableBlock`
- `BlockCapacity`
- `CapacityHold`

## Testing

Run tests:
```bash
python -m pytest core/tests/test_capacity_helpers.py -v
python -m pytest core/tests/test_client_admin_actions.py -v
```

Test coverage:
- Capacity calculation with bookings and holds
- Expired hold purging
- Default duration retrieval
- Block listing
- Admin actions (disable/remove login)
- Client field (can_self_reschedule)

## API Reference

### capacity_helpers.py

```python
from core.capacity_helpers import (
    get_default_duration_minutes,  # Get service duration
    list_blocks_for_date,           # List blocks for a date
    block_remaining_capacity,       # Calculate remaining slots
    create_hold,                    # Create temporary hold
)

# Example
blocks = list_blocks_for_date(date.today())
for block in blocks:
    remaining = block_remaining_capacity(block, "walk")
    print(f"{block.label}: {remaining} slots available")
```

### views_portal.py

```python
# AJAX endpoint
GET /portal/blocks/?date=2025-10-08&service_code=walk
Response: {"blocks": [{"id": 1, "label": "Morning", "remaining": 3, ...}]}

# Start checkout
POST /portal/checkout/start/
Body: {service_code, block_id, price_cents}
Response: {client_secret, hold_token}

# Finalize booking
POST /portal/checkout/finalize/
Body: {service_code, block_id, price_cents, hold_token, payment_intent_id}
Response: {ok: true, booking_id, redirect}
```

## Future Enhancements

Potential additions not included in this PR:
- Time-limited reschedule permissions (X hours before booking)
- Regulars-only time blocks
- Waitlist functionality
- Automated capacity adjustment based on staff availability
- Email notifications for capacity changes
