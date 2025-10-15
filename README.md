# New Farm Dog Walking App

[➡️ Release/deploy checklist](docs/release.md)

[![Tests](https://github.com/ManBearJordan/NewFarmDogWalkingApp/actions/workflows/tests.yml/badge.svg)](https://github.com/ManBearJordan/NewFarmDogWalkingApp/actions/workflows/tests.yml)

A Django-based desktop application that syncs Stripe subscriptions and invoices into bookings and calendar entries. The app provides both a web interface and can be packaged as a desktop application using PyWebView.

## Built-in periodic Stripe sync (no external scheduler)

The app can keep Stripe data fresh **by itself** using a lightweight in-process scheduler.

**Environment**
```
STARTUP_SYNC=1
PERIODIC_SYNC=1
SYNC_INTERVAL_MINUTES=15
```

**Deploy**
1) Add the env flags above to your `.env` (not committed).
2) `pip install -r requirements.txt`
3) Restart your normal launcher (Waitress, etc.). The app will:
   - run a one-off sync shortly after boot (if `STARTUP_SYNC=1`)
   - run a periodic sync every N minutes (if `PERIODIC_SYNC=1`)



## Quick Start

### Prerequisites
- Python 3.8 or higher
- Stripe account (test mode recommended for development)

### 1. Clone and Set Up Environment

```bash
git clone https://github.com/ManBearJordan/NewFarmDogWalkingApp.git
cd NewFarmDogWalkingApp
```

Create a virtual environment:
```bash
python -m venv venv
```

Activate the virtual environment:
- **Windows**: `venv\Scripts\activate`
- **macOS/Linux**: `source venv/bin/activate`

Install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` and update the settings, particularly:
- `DJANGO_SECRET_KEY`: Generate a new secret key for production
- `STRIPE_API_KEY`: Your Stripe API key (see Stripe setup below)

### 3. Database Setup

Run database migrations:
```bash
python manage.py migrate
```

Create a superuser account:
```bash
python manage.py createsuperuser
```

### 4. Stripe Key Setup

You can configure your Stripe API key in two ways:

#### Option A: Environment Variable (Recommended for Production)
Set `STRIPE_API_KEY` in your `.env` file:
```bash
STRIPE_API_KEY=sk_test_your_key_here
```

#### Option B: Admin Interface (Recommended for Development)
1. Start the development server:
   ```bash
   python manage.py runserver
   ```

2. Navigate to `http://localhost:8000/admin/` and log in with your superuser account

3. Go to the Stripe configuration section or visit `http://localhost:8000/stripe/`

4. Paste your Stripe secret key (test keys start with `sk_test_`, live keys start with `sk_live_`)

5. Click "Update Key" to save

### 5. Start the Development Server

```bash
python manage.py runserver
```

The application will be available at `http://localhost:8000/`

### 6. Creating a Test Client

1. Go to the admin interface at `http://localhost:8000/admin/`
2. Navigate to "Clients" and click "Add client"
3. Fill in the client details (name, email, phone)
4. Optionally link to a User account for portal access
5. Save the client

For portal access, ensure the client has a linked User account and that user can log in at `http://localhost:8000/accounts/login/`

## Key Features

- **Stripe Integration**: Automatically sync subscriptions and invoices
- **Booking Management**: Convert Stripe data into calendar bookings
- **Client Portal**: Allow clients to view and create bookings
- **Admin Interface**: Manage clients, bookings, and system settings
- **Desktop App**: Can be packaged as a standalone desktop application

## Development

### Running Tests
Run tests with coverage (writes `coverage.xml`):

```bash
pytest --maxfail=1 --disable-warnings -q
```

The CI-ready coverage report is written to `coverage.xml`. You can add a badge later via Shields.io/CI.

### Database Reset
If you need to reset the database:
```bash
rm app.db
python manage.py migrate
python manage.py createsuperuser
```

### Development Scripts
- `scripts/run_dev.ps1` (Windows PowerShell) - Load .env and start server
- Check `docs/` folder for detailed documentation



## Documentation

- `docs/ARCHITECTURE.md` - System architecture and design decisions
- `docs/portal.md` - Client portal usage guide
- `docs/ops.md` - Operations and deployment guide
- `SECURITY.md` - Security considerations
- `CONTRIBUTING.md` - Contribution guidelines

## Support

For issues and feature requests, please use the GitHub issue tracker.