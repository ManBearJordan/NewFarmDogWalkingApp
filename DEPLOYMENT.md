# Deployment Guide

This repository has been organized to separate development files from production deployment files.

## Production Deployment Files

The following files are essential for production deployment and are located in the root directory:

### Core Application Files:
- `app.py` - Main application entry point
- `db.py` - Database operations
- `stripe_integration.py` - Payment processing
- `stripe_invoice_bookings.py` - Invoice management
- `reports_tab.py` - Reporting functionality
- `reports.py` - Report generation
- `bookings_two_week.py` - Booking management
- `date_range_helpers.py` - Date utilities
- `unified_booking_helpers.py` - Booking helper functions
- `ics_export.py` - Calendar export functionality
- `google_sync.py` - Google integration

### Configuration Files:
- `requirements.txt` - Python dependencies
- `settings.json` - Application settings
- `secrets_config.example.py` - Template for secrets configuration
- `credentials.json` - API credentials template
- `.gitignore` - Git ignore rules

### Utility Files:
- `check_customers.py` - Customer verification utility
- `app_complete.py` - Complete application bundle (alternative entry)

## Development Files (Excluded from Deployment)

The `dev/` directory contains files useful for development and maintenance but should **NOT** be included in production deployments:

### `/dev/tests/` - Test Files
- All `test_*.py` files for automated testing
- Keep for regression testing and bug fixes

### `/dev/docs/` - Documentation
- `*.md` files with implementation notes
- `README*.txt` files with setup instructions
- Keep for developer reference

### `/dev/scripts/` - Maintenance Scripts  
- `cleanup_*.py` and `cleanup_*.sql` - Database cleanup scripts
- `fix_*.py` - Bug fix scripts
- `debug_*.py` - Debugging utilities
- `verify_*.py` and `verify_*.sql` - Data verification scripts
- `Import-*.py` and `Import-*.bat` - Data import utilities
- `*.bat` files - Windows batch scripts
- `*.csv` files - Reference data for imports

### `/dev/backups/` - Backup Files
- `app_backup*.py` - Previous versions of main app
- These are superseded by Git version control

### `/dev/tools/` - Development Tools
- Data import and generation utilities
- CSV processing tools
- Keep if you plan to import more data or patch the app

### `/dev/patches/` - Patch Scripts
- One-time fixes and updates
- Keep if maintenance may be needed again

## Deployment Best Practices

1. **Production Package**: Only include root directory files in your deployment package
2. **Exclude dev/ Directory**: Use deployment tools that respect `.deployment-ignore` or manually exclude `dev/`
3. **Keep Development Files**: Maintain the `dev/` directory in your source repository for future maintenance
4. **Version Control**: Use Git tags for production releases
5. **Environment Setup**: Copy `secrets_config.example.py` to `secrets_config.py` and configure for your environment

## Creating a Production Build

To create a production deployment package:

```bash
# Option 1: Use git archive (recommended)
git archive --format=zip --output=production-release.zip HEAD --exclude=dev/

# Option 2: Copy files manually (exclude dev/ directory)
rsync -av --exclude='dev/' --exclude='.git/' ./ production-build/

# Option 3: Use deployment-ignore file with compatible tools
# Many deployment tools can use .deployment-ignore to exclude files
```

This ensures only essential files are included in production deployments while keeping all development resources available in the source repository.