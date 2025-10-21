# Subscription Repeats Feature

## Overview
This feature adds explicit repeats patterns (weekly/fortnightly) to subscription schedules, allowing bookings to be materialized based on a repeating pattern rather than the Stripe billing cycle.

## Key Components

### 1. Model Changes (`core/models.py`)
Added to `StripeSubscriptionSchedule`:
- `repeats` - CharField with choices: "weekly" or "fortnightly" (default: "weekly")
- `days` - Comma-separated weekdays (e.g., "MON,THU")
- `start_time` - Time in HH:MM format (24-hour)
- `location` - Location for bookings
- `visits_per_fortnight` - Informational field (not used for frequency calculation)

Helper methods:
- `parsed_days()` - Returns list of weekday integers (0=Mon, 6=Sun), falls back to [2] (WED)
- `parsed_time()` - Returns datetime.time object, falls back to 10:30
- `interval_weeks()` - Returns 1 for weekly, 2 for fortnightly

### 2. Migration (`core/migrations/0018_add_repeats_to_schedule.py`)
Adds the new fields to the database with appropriate defaults and constraints.

### 3. Subscription Materializer (`core/subscription_materializer.py`)
Main function: `materialize_future_holds(now_dt=None)`

**Behavior:**
- Creates bookings for the next 8 weeks (HORIZON_WEEKS constant)
- Uses schedule's `repeats` field to determine frequency:
  - Weekly: Creates bookings every week
  - Fortnightly: Creates bookings every 2 weeks
- Uses `days` field to determine which weekdays
- Uses `start_time` for booking start
- Uses Service.duration_minutes for booking end time
- Uses `location` field for booking location (defaults to "Home")
- **Idempotent**: Won't duplicate existing bookings (checks client+service+start_dt)

**Fallbacks:**
- Days: Defaults to [WED] if missing/invalid
- Time: Defaults to 10:30 if missing/invalid
- Location: Defaults to "Home" if missing

### 4. Stripe Integration (`core/stripe_subscriptions.py`)
Function: `upsert_subscription_schedule_from_stripe(sub)`

Reads from Stripe subscription metadata:
- `days` - Weekdays pattern
- `start_time` - Start time
- `location` - Location
- `visits_per_fortnight` - Informational count
- `repeats` - "weekly" or "fortnightly"

If metadata is missing, existing values are preserved or defaults are used.

### 5. Admin Interface
Updated `core/subscription_admin.py` and template:
- Shows repeats dropdown (Weekly/Fortnightly)
- Input for days (e.g., "MON,WED,FRI")
- Input for start time (text field, format HH:MM)
- Input for location

**Backward Compatibility:**
- Still saves weekday/time_of_day to StripeSubscriptionLink for legacy support
- Existing tests continue to pass

### 6. Sync Command (`core/management/commands/sync_all.py`)
Now calls `materialize_future_holds()` after other sync operations.

## Usage Examples

### Setting up a weekly subscription
```python
from core.models import StripeSubscriptionSchedule

schedule.days = "MON,WED,FRI"
schedule.start_time = "10:00"
schedule.location = "Park"
schedule.repeats = "weekly"
schedule.save()
```

### Setting up a fortnightly subscription
```python
schedule.days = "TUE,THU"
schedule.start_time = "14:30"
schedule.location = "Beach"
schedule.repeats = "fortnightly"
schedule.save()
```

### Running materialization
```python
from core.subscription_materializer import materialize_future_holds

result = materialize_future_holds()
print(f"Created {result['created']} bookings")
```

## Testing
Run subscription tests:
```bash
pytest core/tests/test_subscription_materializer.py
pytest core/tests/test_subscription_workflow_integration.py
pytest core/tests/test_subscription_admin.py
```

## Database Schema
The changes are backward compatible. Existing schedules will:
- Have `repeats` default to "weekly"
- Continue using `weekdays_csv` and `default_time` if `days`/`start_time` are not set
- Work with both old and new materializer logic

## Performance Considerations
- Materialization creates bookings 8 weeks ahead
- Uses `select_related` to minimize database queries
- Checks for existing bookings before creating (idempotent)
- Can be run multiple times safely without creating duplicates
