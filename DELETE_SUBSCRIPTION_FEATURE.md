# Delete Subscription Feature Documentation

## Overview

The Delete Subscription feature allows users to remove subscriptions from the application, cleaning up all associated data locally and optionally canceling the subscription in Stripe.

## Feature Components

### 1. Delete Subscription Button

- **Location**: Subscriptions tab, in the top button row
- **Styling**: Red background (`#dc3545`) to indicate destructive action
- **Accessibility**: Requires subscription selection to be enabled

### 2. Confirmation Dialog

The feature includes a comprehensive confirmation dialog that shows:

- Subscription ID
- Customer name
- Clear description of what will be deleted:
  - Future bookings from the subscription
  - Calendar entries
  - Subscription schedules
  - Stripe subscription (configurable)

### 3. Local Database Cleanup

The `delete_subscription_locally()` function handles:

- **Future bookings**: Removes only bookings with `start_dt >= current date`
- **Calendar entries**: Removes future `sub_occurrences` entries
- **Subscription schedules**: Removes from `sub_schedules` and `subs_schedule` tables
- **Past data preservation**: Historical bookings and calendar entries are preserved

### 4. Stripe Integration

The `cancel_subscription()` function:

- Cancels the subscription immediately in Stripe
- Returns success/failure status
- Handles errors gracefully without blocking local deletion

### 5. Automatic Synchronization

After deletion, the system:

- Triggers automatic sync to fetch any missing subscriptions from Stripe
- Shows schedule completion dialogs for subscriptions missing required data
- Updates UI components (calendar, bookings tabs)

## Usage Workflow

1. **Select Subscription**: User selects a subscription row in the table
2. **Click Delete**: User clicks the "Delete Subscription" button
3. **Confirm Action**: User confirms deletion in the dialog
4. **Local Cleanup**: System removes local database entries
5. **Stripe Cancellation**: System attempts to cancel in Stripe (optional)
6. **UI Updates**: System refreshes calendar and bookings tabs
7. **Auto Sync**: System fetches latest subscriptions from Stripe

## Configuration Options

The feature supports configuration for:

- **Stripe Cancellation**: Can be made optional based on user preference
- **Sync Behavior**: Auto-sync after deletion can be disabled if needed
- **Confirmation Dialog**: Message text can be customized

## Error Handling

The feature includes robust error handling for:

- **Missing Selection**: Warns user to select a subscription
- **Invalid Subscription ID**: Validates subscription ID format
- **Database Errors**: Shows error message if local deletion fails
- **Stripe Errors**: Continues with local deletion even if Stripe fails
- **Network Issues**: Gracefully handles sync failures

## Testing

The feature includes comprehensive tests for:

- Local deletion functionality
- Stripe cancellation success and failure scenarios
- Database cleanup verification
- Future vs. past data handling
- Error conditions and edge cases

## Code Structure

### Files Modified

1. **`app.py`**: Added delete button and `delete_subscription()` method to `SubscriptionsTab`
2. **`stripe_integration.py`**: Added `cancel_subscription()` function
3. **`unified_booking_helpers.py`**: Added `delete_subscription_locally()` function

### Files Added

1. **`test_delete_subscription.py`**: Comprehensive test suite

## Security Considerations

- **Confirmation Required**: Cannot delete without explicit user confirmation
- **Data Preservation**: Historical data is preserved, only future data is removed
- **Stripe Safety**: Stripe cancellation includes proper error handling
- **Database Integrity**: Uses transactions to ensure consistent state

## Future Enhancements

Potential future improvements:

1. **Batch Deletion**: Allow deletion of multiple subscriptions
2. **Soft Delete**: Option to mark as deleted instead of permanent removal
3. **Undo Functionality**: Ability to restore recently deleted subscriptions
4. **Audit Trail**: Log subscription deletions for compliance
5. **Advanced Filters**: Better selection tools for bulk operations

## Troubleshooting

### Common Issues

1. **Button Not Responding**: Ensure a subscription is selected in the table
2. **Stripe Errors**: Check network connection and API key configuration
3. **Database Errors**: Verify database permissions and disk space
4. **Sync Issues**: Check Stripe API connectivity for auto-sync

### Debug Information

The feature logs important events:

- Local deletion results (counts of items deleted)
- Stripe cancellation success/failure
- Auto-sync trigger and results
- Error messages with context

## API Reference

### `delete_subscription_locally(conn, sub_id)`

Deletes subscription data from local database.

**Parameters:**
- `conn`: SQLite database connection
- `sub_id`: Stripe subscription ID

**Returns:**
```python
{
    'bookings_deleted': int,
    'calendar_entries_deleted': int,
    'schedules_deleted': int
}
```

### `cancel_subscription(subscription_id)`

Cancels subscription in Stripe.

**Parameters:**
- `subscription_id`: Stripe subscription ID

**Returns:**
- `bool`: True if successful, False otherwise
