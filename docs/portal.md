# Client Portal Guide

The client portal provides a self-service interface for clients to view their bookings, create new bookings, and manage their account information.

## Linking a User to a Client

To enable portal access for a client, you need to link a Django User account to a Client record:

### Method 1: Admin Interface
1. Navigate to the Django admin at `/admin/`
2. Find or create a **User** account:
   - Go to **Users** → **Add user**
   - Set username, password, and email
   - Save the user
3. Edit the **Client** record:
   - Go to **Clients** → find your client → **Edit**
   - Set the **User** field to the user you just created
   - Save the client

### Method 2: During Client Creation
1. Go to **Clients** → **Add client**
2. Fill in the client details (name, email, phone)
3. In the **User** field, select an existing user or leave blank
4. Save the client
5. If you left the User field blank, edit the client later to add the user link

### User Account Requirements
- The user must have a username and password
- The email should ideally match the client's email for consistency
- The user does NOT need staff or superuser permissions for portal access

## Login Flow

### Client Login Process
1. Client navigates to `/accounts/login/`
2. Client enters username and password
3. Upon successful authentication, Django redirects to `/portal/` (configured in `settings.LOGIN_REDIRECT_URL`)
4. The portal checks if the logged-in user is linked to a client profile
5. If linked: Portal displays the client's dashboard
6. If not linked: Portal shows "Your login is not linked to a client profile"

### Portal Home Page
The portal home page (`/portal/`) displays:
- Welcome message with client name
- Current bookings (upcoming and recent)
- Links to create new bookings
- Account information

### Authentication Requirements
- All portal pages require login (`@login_required` decorator)
- Session-based authentication using Django's built-in auth system
- CSRF protection is enabled for all forms

## Creating Bookings

### Booking Creation Process
1. Client clicks "Create New Booking" from the portal home
2. System loads the booking form at `/portal/booking/create/`
3. Form displays available services from live Stripe catalog
4. Client selects:
   - Service type (from Stripe prices)
   - Date and time
   - Location
   - Any special notes

### Service Selection
- Services are loaded from the live Stripe catalog
- Each service shows name and price (e.g., "Dog Walk - $25.00")
- Services are identified by Stripe `price_id` for consistency
- Only active Stripe prices are displayed

### Availability Checking
The system checks for conflicts before allowing booking:
- **Booking conflicts**: Existing bookings that overlap with the requested time
- **Subscription holds**: Active `SubOccurrence` records that might conflict
- Time conflicts are checked across all clients (not just the requesting client)

### Booking Confirmation
After successful booking creation:
1. System creates the booking record
2. Applies credit-first billing (uses available client credits before invoicing)
3. Creates Stripe invoice if payment is due
4. Redirects to confirmation page at `/portal/booking/confirm/`
5. Confirmation page shows:
   - Booking details (service, time, location)
   - Payment status
   - Invoice link (if payment is due)

## Invoice Links

### Invoice Access
When a booking requires payment:
1. System creates a Stripe invoice
2. Generates a hosted invoice URL (public, no login required)
3. Displays the invoice link on the confirmation page
4. Client can click the link to pay via Stripe's hosted payment page

### Invoice Features
- **Hosted Payment**: Stripe handles the payment process
- **No Account Required**: Clients don't need Stripe accounts to pay
- **Payment Methods**: Supports cards, bank transfers (depending on Stripe setup)
- **Automatic Updates**: Payment status syncs back to the booking

### Invoice URL Format
- **Test mode**: `https://invoice.stripe.com/i/acct_test_.../test_...`
- **Live mode**: `https://invoice.stripe.com/i/acct_live_.../live_...`

## Portal Navigation

### Available Pages
- `/portal/` - Home dashboard
- `/portal/booking/create/` - Create new booking
- `/portal/booking/confirm/` - Booking confirmation (after creation)
- `/accounts/login/` - Login page
- `/accounts/logout/` - Logout (redirects to login)

### Navigation Security
- All portal pages require authentication
- Users can only see their own client's data
- No access to admin functions or other clients' information
- Session timeouts follow Django's default settings

## Troubleshooting

### "Not linked to a client profile" Error
This error appears when a user logs in but isn't linked to a Client record:
1. Go to admin → Clients
2. Find the appropriate client
3. Set the User field to the logged-in user
4. Save the client

### Booking Creation Fails
Common issues:
- **Time conflict**: Another booking or subscription hold exists at that time
- **Invalid service**: Selected service is no longer active in Stripe
- **Stripe configuration**: API key is invalid or not set

### Payment Issues
- Ensure Stripe key is configured correctly
- Check that Stripe account can create invoices
- Verify webhook endpoints are configured (for payment status updates)

## Development Notes

### Key Views
- `portal_home()` - Main dashboard
- `portal_booking_create()` - Booking form and processing
- `portal_booking_confirm()` - Post-booking confirmation

### Authentication Flow
- Uses Django's built-in authentication (`django.contrib.auth`)
- Login URL: `/accounts/login/` (configured in `settings.LOGIN_URL`)
- Login redirect: `/portal/` (configured in `settings.LOGIN_REDIRECT_URL`)
- Logout redirect: `/accounts/login/` (configured in `settings.LOGOUT_REDIRECT_URL`)

### Data Flow
1. User authentication via Django auth
2. Client lookup via `user.client_profile` relationship
3. Booking creation through `create_bookings_from_rows()` helper
4. Stripe integration for service catalog and invoicing