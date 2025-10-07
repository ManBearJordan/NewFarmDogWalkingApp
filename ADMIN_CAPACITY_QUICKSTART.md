# Admin Capacity Management - Quick Start Guide

## Quick Setup (5 minutes)

### Step 1: Define Service Defaults
Go to Django Admin > Service Defaults > Add

Example entries:
- `walk` - 60 minutes
- `daycare` - 480 minutes (8 hours)
- `overnight` - 1440 minutes (24 hours)

### Step 2: Access Capacity Editor
Visit: `http://yourdomain.com/admin/capacity/`

You'll see a date picker (defaults to today).

### Step 3: Create Time Blocks
For example, for today:

**Morning Block:**
- Start: 09:00
- End: 12:00
- Label: "Morning Run"
- Click "Add block"

**Afternoon Block:**
- Start: 13:00
- End: 16:00
- Label: "Afternoon Walk"
- Click "Add block"

### Step 4: Set Capacities
For each block, set capacity per service:

**Morning Run block:**
- Service code: `walk`
- Capacity: 5
- Click "Save capacity"

**Afternoon Walk block:**
- Service code: `walk`
- Capacity: 3
- Click "Save capacity"

### Step 5: Copy to Future Days
To set up tomorrow:
1. Change date in URL: `?date=2025-10-09`
2. Click "Copy yesterday"
3. Adjust capacities if needed

## Client Login Controls

### Disable a Client's Login
1. Go to Django Admin > Clients
2. Select client(s)
3. Choose action: "Disable portal login"
4. Click "Go"

Result: User account is deactivated (user.is_active = False)

### Remove a Client's Login
1. Go to Django Admin > Clients
2. Select client(s)
3. Choose action: "Remove portal login"
4. Click "Go"

Result: User account is unlinked from client (but not deleted)

### Enable Self-Reschedule
1. Go to Django Admin > Clients
2. Edit a client
3. Check "Can self reschedule"
4. Save

## Portal Pre-pay Booking Flow

### For Clients
1. Visit `/portal/bookings/new-prepay/`
2. Select service
3. Choose date
4. See available time blocks with real-time capacity
5. Enter details
6. Pay via Stripe
7. Booking created after successful payment

### For Admins
- Monitor capacity at `/admin/capacity/`
- View bookings in Django Admin > Bookings
- Check holds in Django Admin > Capacity Holds (expire after 10 min)

## Key Concepts

### Capacity Calculation
```
Remaining = Block Capacity - Active Bookings - Active Holds
```

### Booking Types
- **Standard Portal**: Uses existing flow, credit-first + invoice
- **Pre-pay Portal**: New flow, payment before booking, no invoice

### Time Blocks
- Completely flexible (no fixed windows)
- Define per day
- Copy from previous days for convenience
- Set different capacities per service

## URLs Reference

- `/admin/capacity/` - Capacity editor
- `/admin/capacity/?date=2025-10-08` - Specific date
- `/portal/bookings/new-prepay/` - Pre-pay booking form
- `/portal/blocks/?date=...&service_code=...` - AJAX capacity check

## Troubleshooting

**Q: Clients can't see available blocks**
A: Ensure blocks are defined for that date with capacity > 0

**Q: Capacity shows as 0 but no bookings exist**
A: Check BlockCapacity records - must define capacity per service

**Q: Holds not expiring**
A: Holds expire after 10 minutes automatically when capacity is checked

**Q: Client login disabled but still accessing portal**
A: Clear browser cache/cookies; user.is_active must be False

## Admin Tips

1. **Set up templates**: Create common day patterns (e.g., "Weekday", "Weekend")
2. **Monitor capacity**: Check `/admin/capacity/` regularly
3. **Bulk setup**: Use "Copy yesterday" to quickly set up multiple days
4. **Adjust on the fly**: Edit capacities anytime; changes are immediate
5. **Review holds**: Check Django Admin > Capacity Holds for stuck holds

## Next Steps

1. Set up service defaults for your services
2. Define blocks for the next week
3. Test the pre-pay flow in a test environment
4. Configure Stripe.js in portal_booking_form_prepay.html
5. Add your Stripe publishable key to the template
