# Unified Subscription-Driven Booking and Calendar Generation

## Overview

This document describes the new unified workflow where Stripe subscriptions are the single source of truth for all bookings and calendar entries. This replaces the previous system that relied on manual sync scripts, fallback logic, and label parsing.

## Key Features

### ✅ Single Source of Truth
- **Stripe subscriptions** with properly configured metadata drive all booking and calendar generation
- **No manual intervention** required - sync happens automatically
- **No fallback logic** - subscription metadata must contain canonical service codes
- **No label parsing** - service codes come directly from subscription metadata

### ✅ Automatic Synchronization
- **Startup sync**: All subscriptions are synchronized when the app starts
- **Calendar refresh**: Uses unified sync to update bookings from subscriptions
- **Manual sync**: Button available for immediate synchronization
- **Real-time updates**: Subscription changes trigger booking updates

### ✅ Canonical Service Codes
- All bookings use standardized service codes from the central service map
- Service codes must be specified in subscription metadata
- No inference or guessing of service types from labels

## Architecture

### Core Components

1. **`subscription_sync.py`** - Central synchronization module
2. **`sync_subscriptions_to_bookings_and_calendar()`** - Main sync function
3. **Enhanced database schema** - Tracks subscription source for bookings
4. **Updated UI** - Calendar and booking tabs reflect unified data

### Database Schema

Bookings now include:
- `created_from_sub_id` - Links booking to Stripe subscription
- `source` - Indicates booking source ('subscription', 'manual', etc.)
- `service_type` - Canonical service code
- `service_name` - Human-readable service label

### Subscription Metadata Format

Subscriptions must include the following metadata for proper sync:

```json
{
  "service_code": "WALK_SHORT_SINGLE",
  "days": "MON,WED,FRI", 
  "start_time": "09:00",
  "end_time": "10:00",
  "location": "123 Main St",
  "dogs": "2",
  "notes": "Special instructions"
}
```

**Required Fields:**
- `service_code`: Must be a valid code from the central service map
- `days`: Comma-separated list of days (MON,TUE,WED,THU,FRI,SAT,SUN)
- `start_time`: Start time in HH:MM format
- `end_time`: End time in HH:MM format

**Optional Fields:**
- `location`: Service location address
- `dogs`: Number of dogs (defaults to 1)
- `notes`: Additional notes for the booking

## Workflow

### App Startup
1. Database is initialized with proper schema
2. `sync_on_startup()` is called automatically
3. All active subscriptions are fetched from Stripe
4. Bookings are generated/updated for subscription occurrences
5. Orphaned bookings from cancelled subscriptions are cleaned up

### Calendar Refresh
1. User clicks "Refresh Calendar" button
2. `sync_subscriptions_to_bookings_and_calendar()` is called
3. Progress dialog shows sync statistics
4. Calendar view is updated with latest data

### Manual Subscription Sync
1. User clicks "Sync Subscriptions" button
2. Immediate sync is performed
3. Detailed statistics are shown
4. All views are refreshed

### Booking Creation Flow
```
Stripe Subscription → Extract Metadata → Generate Occurrences → Create/Update Bookings → Update Calendar
```

## Service Code Mapping

The system uses a central service map with 26 standardized service codes:

### Walk Services
- `WALK_SHORT_SINGLE` - Short Walk (Single)
- `WALK_SHORT_PACK5` - Short Walk (Pack x5)  
- `WALK_SHORT_WEEKLY` - Short Walk (Weekly)
- `WALK_LONG_SINGLE` - Long Walk (Single)
- `WALK_LONG_PACK5` - Long Walk (Pack x5)
- `WALK_LONG_WEEKLY` - Long Walk (Weekly)

### Daycare Services
- `DAYCARE_SINGLE` - Doggy Daycare (per day)
- `DAYCARE_PACK5` - Doggy Daycare (Pack x5)
- `DAYCARE_WEEKLY` - Doggy Daycare (Weekly)
- `DAYCARE_FORTNIGHTLY_PER_VISIT` - Doggy Daycare (Fortnightly per visit)

### Home Visit Services
- `HV_30_1X_SINGLE` - Home Visit 30m 1× (Single)
- `HV_30_1X_PACK5` - Home Visit 30m 1× (Pack x5)
- `HV_30_2X_SINGLE` - Home Visit 30m 2× (Single)
- `HV_30_2X_PACK5` - Home Visit 30m 2× (Pack x5)
- `HOME_30WEEKLY` - Home Visit 1/day (weekly)
- `HOME_30_2_DAY_WEEKLY` - Home Visit 2/day (weekly)

### Pickup/Dropoff Services
- `PICKUP_DROPOFF` - Pick up/Drop off
- `PICKUP_DROPOFF_PACK5` - Pick up/Drop off (Pack x5)
- `PICKUP_WEEKLY_PER_VISIT` - Pick up/Drop off (Weekly per visit)
- `PICKUP_FORTNIGHTLY_PER_VISIT` - Pick up/Drop off (Fortnightly per visit)

### Poop Scoop Services
- `SCOOP_ONCE_SINGLE` - Poop Scoop – One-time
- `SCOOP_WEEKLY_MONTH` - Poop Scoop – Weekly (Monthly)
- `SCOOP_FORTNIGHTLY_MONTH` - Poop Scoop – Fortnightly (Monthly)
- `SCOOP_TWICE_WEEKLY_MONTH` - Poop Scoop – Twice Weekly (Monthly)

### Overnight Services
- `BOARD_OVERNIGHT_SINGLE` - Overnight Pet Sitting (Single)
- `BOARD_OVERNIGHT_PACK5` - Overnight Pet Sitting (Pack x5)

## API Reference

### Main Functions

#### `sync_subscriptions_to_bookings_and_calendar(conn=None, horizon_days=90)`
Main synchronization function.

**Parameters:**
- `conn`: Database connection (optional, creates new if None)
- `horizon_days`: Number of days ahead to generate bookings

**Returns:**
- Dictionary with sync statistics (`subscriptions_processed`, `bookings_created`, `bookings_cleaned`)

#### `sync_on_startup(conn=None)`
Startup synchronization with extended horizon.

**Parameters:**
- `conn`: Database connection (optional)

**Returns:**
- Dictionary with sync statistics

#### `extract_service_code_from_metadata(subscription_data)`
Extract service code from subscription metadata.

**Parameters:**
- `subscription_data`: Subscription data from Stripe API

**Returns:**
- Canonical service code or None if not found

#### `extract_schedule_from_subscription(subscription_data)`
Extract schedule information from subscription metadata.

**Parameters:**
- `subscription_data`: Subscription data from Stripe API

**Returns:**
- Dictionary with schedule information

## Error Handling

### Invalid Subscription Data
- Missing customer ID: Logs warning, skips subscription
- Invalid service code: Logs warning, skips subscription  
- Missing schedule: Logs info, skips subscription
- Invalid metadata: Uses safe defaults where possible

### Database Errors
- Connection issues: Graceful error messages to user
- Constraint violations: Idempotent operations prevent duplicates
- Transaction rollback: Ensures data consistency

### Stripe API Errors
- Rate limiting: Handled by Stripe SDK
- Network issues: User-friendly error messages
- Authentication: Clear error messages

## Testing

### Test Coverage
- ✅ Service code extraction from metadata
- ✅ Schedule parsing and occurrence generation
- ✅ Booking creation and updates
- ✅ Cleanup of cancelled subscriptions
- ✅ Full sync process end-to-end
- ✅ Error handling for invalid data
- ✅ Startup sync functionality

### Running Tests
```bash
python3 test_subscription_sync.py
```

## Migration Guide

### From Legacy System
1. **Remove old scripts**: Legacy cleanup/fix scripts have been removed
2. **Update subscriptions**: Ensure all subscriptions have proper metadata
3. **Verify service codes**: All service codes must be from the central map
4. **Test sync**: Use manual sync button to verify functionality

### Subscription Setup
1. Create subscription in Stripe
2. Add required metadata with canonical service codes
3. Test sync in application
4. Verify bookings appear correctly

## Troubleshooting

### Common Issues

**No bookings generated**
- Check subscription metadata format
- Verify service code is valid
- Ensure customer is linked to local client
- Check application logs

**Bookings missing for some days**
- Verify `days` metadata format (comma-separated)
- Check subscription status in Stripe
- Verify date range within horizon

**Duplicate bookings**
- Database constraints prevent duplicates
- Check for multiple sync calls
- Verify subscription IDs are unique

**Wrong service type**
- Check service_code in subscription metadata
- Verify code exists in central service map
- No fallback logic - must be exact match

### Logging
- Application logs sync statistics
- Error details logged for debugging
- Use verbose logging in development

## Best Practices

### Subscription Management
1. Always include complete metadata when creating subscriptions
2. Use canonical service codes from the central map
3. Test new subscriptions with manual sync
4. Monitor sync statistics for issues

### Data Quality
1. Regular cleanup of cancelled subscriptions
2. Periodic verification of service code validity
3. Monitor for orphaned bookings
4. Validate metadata before subscription creation

### Performance
1. Sync runs automatically on startup
2. Manual sync available for immediate updates
3. Configurable horizon days for booking generation
4. Database indexes optimize query performance

## Future Enhancements

### Planned Features
- Real-time subscription webhooks from Stripe
- Advanced scheduling rules (holidays, exceptions)
- Bulk subscription management tools
- Enhanced reporting and analytics

### Extensibility
- Modular design allows easy feature additions
- Clear separation between sync logic and UI
- Comprehensive test coverage enables safe changes
- Well-documented API for integrations