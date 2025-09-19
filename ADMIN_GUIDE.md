# Django Admin Guide for Staff

## Managing Customer Subscriptions

This guide explains how to use the Django admin interface to manage customer subscriptions, update schedules, and ensure bookings are automatically generated.

## Accessing the Admin Interface

1. Navigate to: `http://your-domain.com/admin/`
2. Log in with your staff credentials
3. You'll see the main admin dashboard with sections for Core, Authentication, and Stripe data

## Managing Subscriptions

### Viewing Subscriptions

1. Click on **"Subscriptions"** under the **"Core"** section
2. You'll see a list of all subscriptions with:
   - **Stripe Subscription ID**: Unique identifier from Stripe
   - **Client**: Customer name
   - **Service Name**: Type of service (e.g., "30 Minute Dog Walk")
   - **Status**: Current subscription status (Active, Canceled, etc.)
   - **Schedule Days**: Days of the week (MON,WED,FRI format)
   - **Time Range**: Start and end times
   - **Schedule Dogs**: Number of dogs
   - **Last Sync**: When data was last synchronized

### Filtering Subscriptions

Use the filter panel on the right to:
- Filter by **Status** (Active, Canceled, etc.)
- Filter by **Service Code** (dog_walk_30, etc.)
- Filter by **Number of Dogs**
- Filter by **Date Created**
- Search by customer name or subscription ID

### Editing a Subscription Schedule

1. Click on the **Stripe Subscription ID** to open the subscription
2. You'll see the subscription details organized in sections:

#### Subscription Information
- Basic details (read-only)
- Client information
- Status (can be changed)

#### Service Configuration
- **Service Code**: Must match your service catalog
- **Service Name**: Human-readable description

#### Schedule Settings
This is where you can update the schedule details:

**Important formatting rules:**
- **Days**: Use 3-letter codes separated by commas (e.g., `MON,WED,FRI`)
  - Valid codes: MON, TUE, WED, THU, FRI, SAT, SUN
- **Times**: Use 24-hour format (e.g., `14:30` for 2:30 PM)
- **Location**: Full address where service will be provided
- **Dogs**: Number of dogs (minimum 1)
- **Notes**: Special instructions for dog walkers

### Automatic Booking Generation

When you save changes to a subscription's schedule:
1. **Automatic Updates**: New bookings are generated automatically
2. **Background Processing**: This happens in the background
3. **Confirmation**: You'll see a message confirming the update
4. **Check Results**: Visit the Bookings section to see new appointments

### Automatic Processing

The system now handles subscription management automatically:

1. **Automatic Sync**: Subscription data is synchronized with Stripe automatically when the app starts
2. **Automatic Booking Generation**: When you save schedule changes, bookings are created automatically
3. **No Manual Actions Required**: The manual sync and booking generation buttons have been removed as they are no longer needed

## Managing Clients

### Viewing Client Information

1. Click **"Clients"** under Core
2. View client details including:
   - Contact information
   - Credit balance (displayed in dollars)
   - Total revenue
   - Service count

### Editing Client Details

- Click on a client name to edit their information
- Update contact details, addresses, etc.

## Managing Bookings

### Viewing Bookings

1. Click **"Bookings"** under Core
2. See all scheduled appointments with:
   - Client name
   - Service details
   - Date and time
   - Location
   - Status
   - Invoice information

### Booking Actions

Select bookings and use actions to:
- **Mark as Completed**: For finished services
- **Mark as Canceled**: For canceled appointments
- **Create Invoices**: Generate billing for completed services

## Common Workflows

### Changing a Customer's Schedule

**Example**: Customer wants to change from Mon/Wed/Fri to Tue/Thu/Sat

1. Go to **Subscriptions** and find the customer
2. Click on their **Subscription ID**
3. In the **Schedule Settings** section:
   - Change **Schedule days** from `MON,WED,FRI` to `TUE,THU,SAT`
   - Update times if needed
   - Modify location or notes as required
4. Click **"Save"**
5. System automatically generates new bookings
6. Check **Bookings** section to verify new schedule

### Adding Special Instructions

1. Open the subscription
2. In **Schedule Settings**, update the **Schedule notes** field
3. Add specific instructions like:
   - "Dog is nervous around other dogs"
   - "Gate code is 1234"
   - "Please text when arriving"
4. Save the changes

### Handling Service Changes

**Example**: Customer upgrades from 30-minute to 60-minute walks

1. Open the subscription
2. Update **Service Code** (e.g., from `dog_walk_30` to `dog_walk_60`)
3. Update **Service Name** accordingly
4. Adjust **Schedule Duration** by changing end time
5. Save to generate new bookings with correct duration

## Troubleshooting

### Bookings Not Generating

If bookings aren't created after saving:
1. Check that schedule fields are properly formatted
2. Verify the subscription status is "Active"
3. Wait a few moments as booking generation happens automatically in the background
4. Refresh the Bookings page to see new appointments
5. Contact technical support if bookings still don't appear

### Schedule Validation Errors

Common errors and fixes:
- **Invalid days format**: Use MON,TUE,WED format (no spaces)
- **Invalid time**: Use HH:MM format (e.g., 09:30, not 9:30am)
- **End time before start time**: Check time order

### Sync Issues

If data seems out of date:
1. Restart the application to trigger automatic sync
2. Check the **Last Sync** column for timing
3. Contact technical support if issues persist - manual sync actions have been removed as they are no longer needed

## Tips for Staff

1. **Always double-check** schedule changes before saving
2. **Use consistent formatting** for days and times
3. **Add detailed notes** for special requirements
4. **Check the Bookings section** after making changes
5. **Use filters** to quickly find specific subscriptions
6. **Regular sync** helps keep data current

## Getting Help

If you encounter issues:
1. Check this guide first
2. Use the admin **History** link to see what changed
3. Contact technical support with:
   - Subscription ID
   - What you were trying to do
   - Error messages received

---

*This guide covers the essential admin workflows for managing subscriptions. The system automatically handles the technical details of booking generation and Stripe synchronization.*
