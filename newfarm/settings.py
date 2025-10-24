import os
import sys
from pathlib import Path
from typing import Tuple, Optional
from dotenv import load_dotenv
import json

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# -----------------------------------------------------------------------------
# Management command detection - suppress scheduler during mgmt commands
# -----------------------------------------------------------------------------
MANAGEMENT_COMMANDS = {
    "makemigrations", "migrate", "collectstatic", "test", "shell", "check",
    "loaddata", "dumpdata", "createsuperuser", "dbshell",
    "seed_service_windows", "sync_all",
}
IS_MANAGEMENT_CMD = len(sys.argv) > 1 and sys.argv[1] in MANAGEMENT_COMMANDS


# -----------------------------------------------------------------------------
# Simple environment variable helper
# -----------------------------------------------------------------------------
class EnvHelper:
    """Simple helper to read environment variables with type conversion."""
    
    @staticmethod
    def str(key: str, default: str = "") -> str:
        """Get string value from environment."""
        return os.getenv(key, default)
    
    @staticmethod
    def bool(key: str, default: bool = False) -> bool:
        """Get boolean value from environment."""
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() in ("1", "true", "yes", "on")
    
    @staticmethod
    def list(key: str, default: list = None) -> list:
        """Get list value from environment (comma-separated)."""
        if default is None:
            default = []
        value = os.getenv(key)
        if value is None:
            return default
        # Handle both comma-separated strings and already-list format
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return default


env = EnvHelper()

# -----------------------------------------------------------------------------
# Core toggles from environment (fallbacks preserve local dev)
# -----------------------------------------------------------------------------
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret')
DEBUG = os.getenv("DEBUG", "0") == "1"

# Secret admin URL from .env (e.g., DJANGO_ADMIN_URL=sk-hd7a4v0-admin/)
DJANGO_ADMIN_URL = os.getenv('DJANGO_ADMIN_URL', 'django-admin/')

# Moved to after proxy settings section for consistency with PR

INSTALLED_APPS = [
    "newfarm.apps.NewfarmConfig",
    "core.apps.CoreConfig",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

# Auth / login config
LOGIN_URL = '/accounts/login/'
# extra per-project exemptions (regex); core exemptions are in middleware
LOGIN_EXEMPT_URLS = [
    # add project-specific regexes here if needed
    r"^stripe/webhooks/$",  # Stripe webhook endpoint
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Serve static files in production directly from Django (behind Cloudflare)
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Force-login middleware MUST come after AuthenticationMiddleware
    'newfarm.middleware.RedirectAnonymousToLoginMiddleware',
    'core.middleware.ServiceDurationGuardMiddleware',
    'core.middleware.cloudflare_secure.CloudflareProtoMiddleware',
    'core.middleware.request_id.RequestIDMiddleware',
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
        'DIRS': [BASE_DIR / 'templates'],
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
# Compressed, cache-busted files for admin + your app
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# MEDIA (only if you use it; otherwise remove)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
# If you have extra local static dirs during dev, uncomment:
# STATICFILES_DIRS = [BASE_DIR / "static"]

# Stripe / App settings
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")  # optional; if set, signatures will be verified
TIME_ZONE = os.getenv("TIME_ZONE", "Australia/Brisbane")
# TTL (seconds) for Stripe catalog cache
STRIPE_CATALOG_TTL_SECONDS = int(os.getenv("STRIPE_CATALOG_TTL_SECONDS", "300"))
# Enable detailed metadata logging for Stripe webhooks (dev/debugging only)
STRIPE_METADATA_LOGGING = env.bool("STRIPE_METADATA_LOGGING", default=False)

# --- Startup sync & background jobs ---
# Trigger one-off subscription sync in AppConfig.ready() when set
STARTUP_SYNC = os.getenv("STARTUP_SYNC", "0") == "1"
# Optional kill switch if needed in ops
DISABLE_SCHEDULER = env.bool("DISABLE_SCHEDULER", default=False)

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
# --- Proxy/HTTPS awareness (Cloudflare Tunnel) ---
USE_X_FORWARDED_HOST = env.bool("USE_X_FORWARDED_HOST", default=True if PRODUCTION else False)
# Trust the proto header set by Cloudflare Tunnel
# In production mode, default to X-Forwarded-Proto; in dev mode, None unless explicitly set
_proxy_header_value = env.list("SECURE_PROXY_SSL_HEADER", default=["HTTP_X_FORWARDED_PROTO", "https"] if PRODUCTION else [])
# Validate that the header is a 2-tuple (header_name, expected_value); fall back to default if malformed
if _proxy_header_value and len(_proxy_header_value) != 2 and PRODUCTION:
    _proxy_header_value = ["HTTP_X_FORWARDED_PROTO", "https"]
SECURE_PROXY_SSL_HEADER = tuple(_proxy_header_value) if _proxy_header_value else None

# Optional: tolerate Cloudflare CF-Visitor if present (middleware also handles this)
CF_VISITOR_HEADER = "HTTP_CF_VISITOR"

# In production, prefer redirect to HTTPS unless explicitly disabled
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True if PRODUCTION else False)

ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS','testserver,localhost,127.0.0.1,app.newfarmdogwalking.com.au').split(',') if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv('CSRF_TRUSTED_ORIGINS','https://app.newfarmdogwalking.com.au').split(',') if o.strip()]

# Extra safety when Cloudflare sends CF-Visitor instead of XFP
def SECURE_PROXY_SSL_HEADER_FALLBACK(get_response):
    def middleware(request):
        # CF-Visitor: {"scheme":"https"}
        cfv = request.META.get('HTTP_CF_VISITOR')
        if cfv and 'https' in cfv:
            request.META['wsgi.url_scheme'] = 'https'
            request.is_secure = lambda: True  # type: ignore
        return get_response(request)
    return middleware

# insert fallback right after SecurityMiddleware if active
MIDDLEWARE.insert(1, 'newfarm.settings.SECURE_PROXY_SSL_HEADER_FALLBACK')

# Cookies/HSTS only when PRODUCTION
SESSION_COOKIE_SECURE = PRODUCTION
CSRF_COOKIE_SECURE = PRODUCTION
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7 if PRODUCTION else 0

# --- Client portal auth ---
# LOGIN_URL is defined earlier in the file
LOGIN_REDIRECT_URL = '/calendar/'
LOGOUT_REDIRECT_URL = "login"

# Basic error email/logging defaults (mail backend configured elsewhere)
ADMINS = [("Admin", env.str("ADMIN_EMAIL", default="admin@newfarmdogwalking.com.au"))]
SERVER_EMAIL = env.str("SERVER_EMAIL", default="server@app.newfarmdogwalking.com.au")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {
            "()": "core.logging_filters.RequestIDLogFilter",
        },
    },
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["request_id"],
        },
    },
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": True},
        "core.scheduler": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "core": {"handlers": ["console"], "level": "INFO"},
    },
}