# NewFarmDogWalkingApp — Clean Rewrite Skeleton

This repo has been reset to a minimal, secure starting point for the desktop/web app.
Key points:
- Stripe secret is read from the STRIPE_SECRET_KEY environment variable.
- Optional secure fallback: system keyring (Windows Credential Manager on Windows).
- No secret keys are committed to the repo.

## Running locally

To set up the development environment:

1. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

2. Activate the virtual environment:
   - On Windows: `venv\Scripts\activate`
   - On macOS/Linux: `source venv/bin/activate`

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run database migrations:
   ```bash
   python manage.py migrate
   ```

5. Start the development server:
   ```bash
   python manage.py runserver
   ```

Local quickstart (user-ready):
1) Install runtime and dependencies listed in requirements.txt.
2) On first app launch the GUI admin will prompt the user to paste their Stripe secret key once.
   The app stores it securely (keyring) and provides an Admin → Stripe Key action to replace it.
3) Platform administrators can set STRIPE_SECRET_KEY in the environment for automated deployments.

## Stripe Test vs Live Mode

The application supports both Stripe test and live modes, determined automatically by your API key prefix:

### Key Formats
- **Test mode keys**: Start with `sk_test_` (e.g., `sk_test_51ABC...`)
- **Live mode keys**: Start with `sk_live_` (e.g., `sk_live_51XYZ...`)

### URL Base Switching
The application automatically switches Stripe Dashboard URLs based on your key mode:
- **Test mode**: URLs point to `https://dashboard.stripe.com/test/invoices/...`  
- **Live mode**: URLs point to `https://dashboard.stripe.com/invoices/...`

This ensures that when you click "View Invoice" links in the app, you're taken to the correct Stripe dashboard environment.

### Setting Your Stripe Key

#### Via Environment Variable (Recommended for deployments)
```bash
export STRIPE_SECRET_KEY=sk_test_your_key_here
```

#### Via Admin Interface (Recommended for local development)
1. Start the application with `python manage.py runserver`
2. Navigate to `/admin/` and log in as a superuser
3. Go to `/admin/stripe/` or look for "Stripe Configuration" 
4. Paste your Stripe secret key (test or live)
5. Click "Update Key" to save

The admin interface will:
- Show the current configuration status (Test/Live/Not configured)
- Display a masked version of your key for security
- Allow you to update the key as needed
- Validate key format before saving

#### Key Storage Priority
The application checks for Stripe keys in this order:
1. **Environment variable** (`STRIPE_SECRET_KEY`) - highest priority
2. **Database storage** (via admin interface) - fallback option

This allows environment variables to override database settings for production deployments while still supporting GUI configuration for development.