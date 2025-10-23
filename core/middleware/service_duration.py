from django.conf import settings
from django.http import HttpResponseRedirect
from django.contrib import messages
from core.models import Service


class ServiceDurationGuardMiddleware:
    """
    If any active Service has no duration, redirect authenticated staff to the setup page.
    Clients are not blocked.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # Normalize the secret admin prefix from env (e.g., "sk-hd7a4v0-admin/")
        admin_env = getattr(settings, "DJANGO_ADMIN_URL", "admin/")
        self.admin_prefix = "/" + admin_env.lstrip("/")
        # Keep a classic /admin/ safety exemption as well
        self.fallback_admin_prefix = "/admin/"

    def __call__(self, request):
        if request.user.is_authenticated and request.user.is_staff:
            path = request.path or "/"

            # --- EXEMPT: Django Admin paths ---
            if path.startswith(self.admin_prefix) or path.startswith(self.fallback_admin_prefix):
                return self.get_response(request)

            # Exempt service settings page and static/media
            exempt_prefixes = ("/settings/services/", "/static/", "/media/")
            if not path.startswith(exempt_prefixes):
                # If any active Service lacks a duration, nudge staff to finish setup
                if Service.objects.filter(is_active=True, duration_minutes__isnull=True).exists():
                    messages.warning(request, "Please set durations for active services before continuing.")
                    return HttpResponseRedirect("/settings/services/")

        return self.get_response(request)
