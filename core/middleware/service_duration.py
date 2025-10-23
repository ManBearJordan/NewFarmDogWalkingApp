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
        # Secret admin path from env (e.g., "sk-hd7a4v0-admin/")
        admin_env = getattr(settings, "DJANGO_ADMIN_URL", "admin/")
        self.admin_prefix = "/" + admin_env.lstrip("/")
        # Classic Django admin fallback
        self.fallback_admin_prefix = "/admin/"
        # Blue-bar staff portal sections to allow without interception
        self.staff_portal_prefixes = (
            "/bookings/",
            "/calendar/",
            "/subscriptions/",
            "/clients/",
            "/pets/",
            "/tags/",
        )
        # Always-safe paths
        self.exempt_prefixes = (
            "/settings/services/",  # where you set durations
            "/static/",
            "/media/",
        )

    def __call__(self, request):
        user = getattr(request, "user", None)
        path = (request.path or "/")

        # Only guard authenticated staff
        if user and user.is_authenticated and user.is_staff:
            # --- EXEMPT: Django Admin and the blue-bar staff portal paths ---
            if (
                path.startswith(self.admin_prefix)
                or path.startswith(self.fallback_admin_prefix)
                or any(path.startswith(p) for p in self.staff_portal_prefixes)
            ):
                return self.get_response(request)

            # Exempt known-safe paths (service settings, static, media)
            if any(path.startswith(p) for p in self.exempt_prefixes):
                return self.get_response(request)

            # If any active service lacks a duration, nudge staff to finish setup
            if Service.objects.filter(is_active=True, duration_minutes__isnull=True).exists():
                messages.warning(request, "Please set durations for active services before continuing.")
                return HttpResponseRedirect("/settings/services/")

        return self.get_response(request)
