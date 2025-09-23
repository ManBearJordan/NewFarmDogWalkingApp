import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret')
DEBUG = True
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']

INSTALLED_APPS = [
    "core.apps.CoreConfig",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'newfarm.urls'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'app.db',
    }
}

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

STATIC_URL = '/static/'

# Stripe / App settings
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")
TIME_ZONE = os.getenv("TIME_ZONE", "Australia/Brisbane")
# TTL (seconds) for Stripe catalog cache
STRIPE_CATALOG_TTL_SECONDS = int(os.getenv("STRIPE_CATALOG_TTL_SECONDS", "300"))

# --- Startup sync & background jobs ---
# Trigger one-off subscription sync in AppConfig.ready() when set
STARTUP_SYNC = os.getenv("STARTUP_SYNC", "0") == "1"

# Celery (optional). If you don't run Celery, leave these blank.
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "")
CELERY_TIMEZONE = TIME_ZONE

# Enable Celery beat schedule if broker is configured AND BEAT flag is on
START_CELERY_BEAT = os.getenv("START_CELERY_BEAT", "0") == "1"

if CELERY_BROKER_URL and START_CELERY_BEAT:
    from celery.schedules import crontab
    CELERY_BEAT_SCHEDULE = {
        # Daily refresh of future occurrences at 02:15 local time
        "daily-subscription-sync": {
            "task": "core.tasks.daily_subscription_sync",
            "schedule": crontab(hour=2, minute=15),
        },
    }

# --- Client portal auth ---
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/portal/"
LOGOUT_REDIRECT_URL = "/accounts/login/"