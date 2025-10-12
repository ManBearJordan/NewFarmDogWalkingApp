import os
from pathlib import Path
from typing import Tuple, Optional
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# -----------------------------------------------------------------------------
# Core toggles from environment (fallbacks preserve local dev)
# -----------------------------------------------------------------------------
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret')
DEBUG = os.getenv("DEBUG", "0") == "1"

_allowed = os.getenv("ALLOWED_HOSTS", "testserver,localhost,127.0.0.1").strip()
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(",") if h.strip()]

_csrf = os.getenv("CSRF_TRUSTED_ORIGINS", "").strip()
CSRF_TRUSTED_ORIGINS = [u.strip() for u in _csrf.split(",") if u.strip()]

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

# -----------------------------------------------------------------------------
# Static files
# -----------------------------------------------------------------------------
# Serve static via IIS: collect to /staticfiles
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# If you have extra local static dirs during dev, uncomment:
# STATICFILES_DIRS = [BASE_DIR / "static"]

# Stripe / App settings
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
TIME_ZONE = os.getenv("TIME_ZONE", "Australia/Brisbane")
# TTL (seconds) for Stripe catalog cache
STRIPE_CATALOG_TTL_SECONDS = int(os.getenv("STRIPE_CATALOG_TTL_SECONDS", "300"))

# --- Startup sync & background jobs ---
# Trigger one-off subscription sync in AppConfig.ready() when set
STARTUP_SYNC = os.getenv("STARTUP_SYNC", "0") == "1"

# ---------------------------
# Celery (background jobs)
# ---------------------------
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = False  # set True in tests if you want sync execution

# Optional daily scheduler (Beat)
START_CELERY_BEAT = os.getenv("START_CELERY_BEAT", "0") == "1"
if START_CELERY_BEAT:
    from datetime import timedelta
    CELERY_BEAT_SCHEDULE = {
        "daily-subscription-sync": {
            "task": "core.tasks.sync_subscriptions_daily",
            "schedule": timedelta(days=1),
            "options": {"expires": 60 * 60},  # 1 hour
        }
    }

# --- Stripe key storage ---
# Prefer OS keyring if available/allowed; otherwise env var + in-memory override.
USE_KEYRING = os.getenv("USE_KEYRING", "0") == "1"
KEYRING_SERVICE_NAME = os.getenv("KEYRING_SERVICE_NAME", "NewFarmDogWalking")
# Contact for non-staff support (used in templates)
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@newfarmdogwalking.example")

# --- Production security toggles ---
PRODUCTION = os.getenv("PRODUCTION", "0") == "1"

# -----------------------------------------------------------------------------
# Reverse-proxy / security
# -----------------------------------------------------------------------------
_sp = os.getenv("SECURE_PROXY_SSL_HEADER")
if _sp and "," in _sp:
    name, val = _sp.split(",", 1)
    SECURE_PROXY_SSL_HEADER: Optional[Tuple[str, str]] = (name.strip(), val.strip())
elif PRODUCTION:
    SECURE_PROXY_SSL_HEADER: Optional[Tuple[str, str]] = ("HTTP_X_FORWARDED_PROTO", "https")
else:
    SECURE_PROXY_SSL_HEADER: Optional[Tuple[str, str]] = None

USE_X_FORWARDED_HOST = os.getenv("USE_X_FORWARDED_HOST", "1" if PRODUCTION else "0") == "1"
if PRODUCTION:
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "1") == "1"
    CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "1") == "1"
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# --- Client portal auth ---
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/portal/"
LOGOUT_REDIRECT_URL = "/accounts/login/"