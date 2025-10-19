import re
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

DEFAULT_EXEMPT = [
    r"^$",  # Allow root path to be handled by root_router
    r"^accounts/login/$",
    r"^accounts/logout/$",
    r"^static/.*",
    r"^media/.*",
    r"^favicon\.ico$",
    r"^health/?$",
    r"^healthz/?$",
    r"^readyz$",
    r"^admin/stripe/.*",
]

def _compile(patterns):
    return [re.compile(p) for p in patterns]

EXEMPT_PATTERNS = _compile(getattr(settings, "LOGIN_EXEMPT_URLS", []) or []) + _compile(DEFAULT_EXEMPT)

class RedirectAnonymousToLoginMiddleware:
    """
    If user is not authenticated, redirect to LOGIN_URL unless path is exempt.
    Place AFTER AuthenticationMiddleware.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path.lstrip("/")

        # Always allow admin path
        admin_path = (getattr(settings, "DJANGO_ADMIN_URL", "admin/")).rstrip("/")
        if admin_path and path.startswith(admin_path):
            return self.get_response(request)

        # Allow exempt paths
        for rx in EXEMPT_PATTERNS:
            if rx.match(path):
                return self.get_response(request)

        # Authenticated: carry on
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            return self.get_response(request)

        # Not authenticated: go to login
        login_url = settings.LOGIN_URL if hasattr(settings, "LOGIN_URL") else "/accounts/login/"
        return redirect(f"{login_url}?next=/{path}")
