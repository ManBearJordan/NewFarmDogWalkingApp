# Django Migration Guide - New Farm Dog Walking App

## Overview

This guide provides step-by-step instructions for migrating the existing PySide6 desktop application to a Django-based monolith structure while preserving all existing functionality.

## ⚠️ IMPORTANT - Migration Safety

**This migration is designed to be:**
- **Incremental**: Django runs alongside existing code
- **Reversible**: Original functionality remains unchanged
- **Non-destructive**: No existing code or data is lost
- **Gradual**: Features can be migrated one at a time

## Architecture Overview

### Before Migration
```
PySide6 Desktop App
├── SQLite Database (app.db)
├── Stripe Integration (stripe_integration.py)
├── Subscription Sync (subscription_sync.py)
├── Booking Management (booking_utils.py)
└── UI Components (app.py, etc.)
```

### After Migration
```
Hybrid Architecture
├── PySide6 Desktop App (unchanged)
├── Django Web Framework
│   ├── Django Admin Interface
│   ├── REST API Endpoints
│   ├── Background Tasks (Celery)
│   └── Enhanced Models
├── Shared SQLite Database (app.db)
└── Stripe Integration (enhanced with dj-stripe)
```

## Prerequisites

### 1. System Requirements
- Python 3.8+ (already installed)
- Redis server (for Celery background tasks)
- Existing requirements.txt dependencies

### 2. Install Redis (Required for Background Tasks)

**Windows:**
```bash
# Download and install Redis for Windows
# Or use Docker: docker run -d -p 6379:6379 redis:alpine
```

**Linux/MacOS:**
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# MacOS
brew install redis
```

### 3. Install New Dependencies
```bash
pip install django djangorestframework dj-stripe celery redis python-decouple
```

## Migration Steps

### Step 1: Backup Current System
```bash
# Backup database
cp app.db app.db.backup.$(date +%Y%m%d_%H%M%S)

# Backup codebase
git add .
git commit -m "Pre-Django migration backup"
```

### Step 2: Initialize Django (Already Done)
The Django project structure has been created:
```
dogwalking_django/
├── __init__.py
├── settings.py
├── urls.py
├── wsgi.py
└── celery.py

core/
├── models.py          # Django models for Client, Subscription, Booking
├── admin.py           # Django admin configuration
├── views.py           # REST API endpoints
├── serializers.py     # API serializers
├── tasks.py           # Celery background tasks
└── management/commands/ # Migration utilities
```

### Step 3: Configure Environment Variables
Create a `.env` file in the project root:
```bash
# .env file
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Stripe Configuration (use existing keys)
STRIPE_LIVE_SECRET_KEY=sk_live_...
STRIPE_TEST_SECRET_KEY=sk_test_...
STRIPE_LIVE_PUBLIC_KEY=pk_live_...
STRIPE_TEST_PUBLIC_KEY=pk_test_...

# dj-stripe webhook secret
DJSTRIPE_WEBHOOK_SECRET=whsec_...

# Celery/Redis Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Step 4: Run Django Migrations
```bash
# Create database tables for Django
python manage.py makemigrations
python manage.py migrate

# Create Django admin superuser
python manage.py createsuperuser
```

### Step 5: Migrate Existing Data
```bash
# Dry run to see what would be migrated
python manage.py migrate_data --dry-run

# Perform actual migration
python manage.py migrate_data --database-path app.db
```

### Step 6: Start Django Services

#### Terminal 1: Django Development Server
```bash
python manage.py runserver 8000
```

#### Terminal 2: Celery Worker
```bash
celery -A dogwalking_django worker --loglevel=info
```

#### Terminal 3: Celery Beat (Periodic Tasks)
```bash
celery -A dogwalking_django beat --loglevel=info
```

#### Terminal 4: Redis Server (if not running as service)
```bash
redis-server
```

### Step 7: Verify Migration Success

1. **Check Django Admin**: Visit http://localhost:8000/admin/
2. **Check API Endpoints**: Visit http://localhost:8000/docs/
3. **Verify Data**: Compare data in Django admin with existing desktop app
4. **Test Existing App**: Ensure desktop app still works unchanged

## Available Features After Migration

### 1. Django Admin Interface
- **URL**: http://localhost:8000/admin/
- **Features**:
  - Client management with financial metrics
  - Subscription management with schedule details
  - Booking management with status tracking
  - Bulk operations and filtering

### 2. REST API Endpoints
- **Base URL**: http://localhost:8000/api/
- **Endpoints**:
  - `/api/clients/` - Client CRUD operations
  - `/api/subscriptions/` - Subscription management
  - `/api/bookings/` - Booking management
  - `/api/schedules/` - Schedule templates
- **Documentation**: http://localhost:8000/docs/

### 3. Background Tasks
- **Automatic subscription syncing** (every hour)
- **Booking generation** for subscriptions
- **Stripe webhook processing**
- **Data cleanup** and maintenance

## Integration with Existing Code

### Existing Code Compatibility
The migration is designed to preserve all existing functionality:

```python
# Existing code continues to work unchanged
from subscription_sync import sync_subscriptions_to_bookings_and_calendar
from stripe_integration import create_draft_invoice_for_booking
from db import get_conn, add_booking

# New Django integration is optional
from core.models import Subscription, Booking
from core.tasks import sync_all_subscriptions
```

### Hybrid Usage Patterns

#### Pattern 1: Desktop App with Django Admin
- Use desktop app for daily operations
- Use Django admin for bulk management and reporting
- Background tasks handle automatic syncing

#### Pattern 2: API Integration
- Desktop app can optionally use Django REST API
- External integrations can use the API
- Mobile app development becomes possible

#### Pattern 3: Gradual Migration
- Migrate individual features over time
- Keep existing code until Django equivalent is proven
- No pressure to migrate everything at once

## Common Tasks

### Sync All Subscriptions
```bash
# Using Django management command
python manage.py sync_subscriptions --horizon-days 90

# Using Celery task (async)
python manage.py sync_subscriptions --async

# Using existing code (still works)
python -c "from subscription_sync import sync_subscriptions_to_bookings_and_calendar; sync_subscriptions_to_bookings_and_calendar()"
```

### Generate Bookings for Subscription
```bash
# Via Django admin interface (bulk actions)
# Via REST API endpoint
# Via Celery task
# Via existing booking_utils.py (unchanged)
```

### Create Invoices
```bash
# Via Django admin (bulk action)
# Via REST API
# Via existing stripe_integration.py (unchanged)
```

## Rollback Procedures

### Emergency Rollback
If something goes wrong, the system can be immediately reverted:

1. **Stop Django services** (Ctrl+C in terminals)
2. **Restore database backup**:
   ```bash
   cp app.db.backup.YYYYMMDD_HHMMSS app.db
   ```
3. **Continue using desktop app** (unchanged)

### Selective Rollback
- Remove Django admin access while keeping API
- Disable background tasks while keeping models
- Use existing code paths exclusively

## Troubleshooting

### Common Issues

#### 1. Database Locked Error
```bash
# Close desktop app completely
# Restart Django server
python manage.py runserver 8000
```

#### 2. Redis Connection Error
```bash
# Start Redis server
redis-server
# Or check if running: redis-cli ping
```

#### 3. Migration Conflicts
```bash
# Reset Django migrations (safe - doesn't affect data)
python manage.py migrate core zero
python manage.py makemigrations
python manage.py migrate
```

#### 4. Stripe Webhook Issues
- Check webhook endpoint URL
- Verify webhook secret in .env file
- Check Stripe dashboard for webhook status

### Debug Mode
Enable detailed logging by setting in .env:
```bash
DEBUG=True
```

## Testing the Migration

### 1. Data Integrity Tests
```bash
# Compare record counts
python -c "
import sqlite3
conn = sqlite3.connect('app.db')
print('Direct SQLite clients:', conn.execute('SELECT COUNT(*) FROM clients').fetchone()[0])
conn.close()

from core.models import Client
print('Django clients:', Client.objects.count())
"
```

### 2. Functionality Tests
- Create a booking in desktop app → Verify it appears in Django admin
- Sync subscriptions via Django → Verify bookings appear in desktop app
- Create invoice via Django admin → Verify in Stripe dashboard

### 3. Performance Tests
- Time subscription sync operations
- Monitor background task performance
- Check database query efficiency

## Production Deployment

### Environment Preparation
```bash
# Use production settings
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Use production database
# Configure proper Redis server
# Set up process monitoring (supervisor, systemd)
```

### Process Management
```bash
# Use production WSGI server
pip install gunicorn
gunicorn dogwalking_django.wsgi:application

# Run Celery with supervisor/systemd
# Set up Redis with persistence
# Configure log rotation
```

## Benefits of Migration

### For Developers
- **Modern Framework**: Django's mature ecosystem
- **Better Testing**: Django's test framework
- **Documentation**: Auto-generated API docs
- **Scalability**: Prepared for growth
- **Maintainability**: Clean separation of concerns

### For Business
- **Web Interface**: Access from any device
- **API Access**: Integration possibilities
- **Automation**: Background task processing
- **Reporting**: Enhanced admin interface
- **Future-Proof**: Foundation for expansion

### For Users
- **Unchanged Workflow**: Desktop app works as before
- **Enhanced Management**: Web-based admin tools
- **Better Reliability**: Automatic sync and error handling
- **Mobile Ready**: API enables mobile app development

## Support and Maintenance

### Code Organization
```
├── Existing Code (unchanged)
│   ├── app.py
│   ├── subscription_sync.py
│   ├── stripe_integration.py
│   └── ... (all existing files)
├── Django Code (new)
│   ├── dogwalking_django/
│   └── core/
└── Shared Resources
    ├── app.db (same database)
    └── requirements.txt (updated)
```

### Documentation
- Django admin interface is self-documenting
- REST API documentation at `/docs/`
- This migration guide
- Existing documentation remains valid

### Updates and Extensions
- Add new Django features without affecting desktop app
- Enhance existing functionality through Django admin
- Build new integrations using REST API
- Mobile app development using existing API

## Conclusion

This Django migration provides a robust foundation for the future while maintaining complete backward compatibility. The desktop application continues to work unchanged, while new capabilities are added through Django's powerful framework.

The migration can be adopted gradually:
1. **Phase 1**: Use Django for administration and reporting
2. **Phase 2**: Leverage background tasks for automation
3. **Phase 3**: Build new features using Django/API
4. **Phase 4**: Optional frontend modernization

**Remember**: This migration is entirely additive. Nothing is removed or broken, and the system can be rolled back at any time.