# Operations: Subscription Sync

## One-off on server startup
Set `STARTUP_SYNC=1` (in `.env`) and the app will run a background sync a few seconds after boot.
This is implemented in `core.apps.CoreConfig.ready()` and guarded to avoid double runs with Django's
autoreloader.

## Manual run (cron, GitHub Actions, etc.)
```
python manage.py sync_subscriptions
```
This calls `subscription_sync.sync_subscriptions_to_bookings_and_calendar()` and prints stats.

### Example crontab (daily at 02:15 local)
```
15 2 * * * source /path/to/venv/bin/activate && cd /path/to/app && ./manage.py sync_subscriptions >> var/log/sync.log 2>&1
```

## Celery (optional)
If you prefer a worker/beat:
1) Set `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` and `START_CELERY_BEAT=1` in `.env`.
2) Run:
```
celery -A newfarm.celery worker -l info
celery -A newfarm.celery beat -l info
```
Beat will run `core.tasks.daily_subscription_sync` daily at **02:15** (AEST/AEDT).

> The sync is idempotent: it clears & rebuilds **future** holds and re-materializes occurrences.

## GitHub Actions / CI Examples

### Daily Sync Workflow
Create `.github/workflows/daily-sync.yml`:

```yaml
name: Daily Subscription Sync

on:
  schedule:
    # Run at 02:15 UTC daily (adjust timezone as needed)
    - cron: '15 2 * * *'
  workflow_dispatch: # Allow manual trigger

jobs:
  sync:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        
    - name: Run database migrations
      run: python manage.py migrate
      env:
        DJANGO_SECRET_KEY: ${{ secrets.DJANGO_SECRET_KEY }}
        STRIPE_API_KEY: ${{ secrets.STRIPE_API_KEY }}
        
    - name: Sync subscriptions
      run: python manage.py sync_subscriptions
      env:
        DJANGO_SECRET_KEY: ${{ secrets.DJANGO_SECRET_KEY }}
        STRIPE_API_KEY: ${{ secrets.STRIPE_API_KEY }}
        TIME_ZONE: 'Australia/Brisbane'
```

### Required Secrets
In your GitHub repository, set these secrets (Settings → Secrets and variables → Actions):
- `DJANGO_SECRET_KEY` - Django secret key for production
- `STRIPE_API_KEY` - Your Stripe API key (use live key for production)

### Backup Workflow
Create `.github/workflows/backup.yml`:

```yaml
name: Database Backup

on:
  schedule:
    # Weekly backup on Sundays at 03:00 UTC
    - cron: '0 3 * * 0'
  workflow_dispatch:

jobs:
  backup:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: Install dependencies
      run: pip install -r requirements.txt
        
    - name: Create backup
      run: |
        python manage.py dumpdata --natural-foreign --natural-primary > backup-$(date +%Y%m%d).json
      env:
        DJANGO_SECRET_KEY: ${{ secrets.DJANGO_SECRET_KEY }}
        
    - name: Upload backup artifact
      uses: actions/upload-artifact@v3
      with:
        name: database-backup-${{ github.run_number }}
        path: backup-*.json
        retention-days: 30
```

### Cron Alternatives

#### System Crontab (Linux/macOS)
```bash
# Edit crontab
crontab -e

# Add entry for daily sync at 2:15 AM
15 2 * * * cd /path/to/NewFarmDogWalkingApp && source venv/bin/activate && python manage.py sync_subscriptions >> /var/log/nfdw-sync.log 2>&1

# Add entry for weekly backup on Sundays at 3:00 AM
0 3 * * 0 cd /path/to/NewFarmDogWalkingApp && source venv/bin/activate && python manage.py dumpdata > backup-$(date +\%Y\%m\%d).json
```

#### Windows Task Scheduler
1. Open Task Scheduler
2. Create Basic Task → "Daily Sync"
3. Set trigger: Daily at 2:15 AM
4. Action: Start a program
   - Program: `C:\path\to\venv\Scripts\python.exe`
   - Arguments: `manage.py sync_subscriptions`
   - Start in: `C:\path\to\NewFarmDogWalkingApp`

#### Systemd Timer (Linux)
Create `/etc/systemd/system/nfdw-sync.service`:
```ini
[Unit]
Description=New Farm Dog Walking Sync
After=network.target

[Service]
Type=oneshot
User=nfdw
WorkingDirectory=/path/to/NewFarmDogWalkingApp
Environment=DJANGO_SECRET_KEY=your-secret-key
Environment=STRIPE_API_KEY=your-stripe-key
ExecStart=/path/to/venv/bin/python manage.py sync_subscriptions
```

Create `/etc/systemd/system/nfdw-sync.timer`:
```ini
[Unit]
Description=Run NFDW sync daily
Requires=nfdw-sync.service

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
sudo systemctl enable nfdw-sync.timer
sudo systemctl start nfdw-sync.timer
```