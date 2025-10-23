from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages
from core.models import Service


class ServiceDurationGuardMiddleware:
    """
    If any active Service has no duration, redirect authenticated staff to the setup page.
    Clients are not blocked.
    
    Exempts /ops/ namespace and legacy staff routes from duration guard checks.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # Secret admin path from env (e.g., "sk-hd7a4v0-admin/")
        admin_env = getattr(settings, "DJANGO_ADMIN_URL", "admin/")
        self.admin_prefix = "/" + admin_env.lstrip("/")
        # Classic Django admin fallback
        self.fallback_admin_prefix = "/admin/"
        
        # Canonical staff namespace
        self.ops_prefix = "/ops/"
        
        # Legacy staff routes - these are exempt from duration guard to maintain backward compatibility
        # The /ops/ namespace provides the new canonical staff interface that redirects to these
        self.legacy_staff_prefixes = (
            "/bookings/",
            "/calendar/",
            "/subscriptions/",
            "/clients/",
            "/pets/",
            "/tags/",
            "/admin-tools/",
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
            # 1) Exempt admin + /ops/ namespace
            if (
                path.startswith(self.admin_prefix)
                or path.startswith(self.fallback_admin_prefix)
                or path.startswith(self.ops_prefix)
            ):
                return self.get_response(request)
            
            # 2) Exempt legacy staff routes (for backward compatibility with bookmarks)
            if any(path.startswith(p) for p in self.legacy_staff_prefixes):
                return self.get_response(request)

            # 3) Exempt safe paths
            if any(path.startswith(p) for p in self.exempt_prefixes):
                return self.get_response(request)

            # 4) If active services are missing durations, nudge to settings
            if Service.objects.filter(is_active=True, duration_minutes__isnull=True).exists():
                messages.warning(request, "Please set durations for active services before continuing.")
                return redirect("/settings/services/")

        return self.get_response(request)
