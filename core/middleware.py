from django.http import HttpResponseRedirect
from django.contrib import messages
from .models import Service


class ServiceDurationGuardMiddleware:
    """
    If any active Service has no duration, redirect authenticated staff to the setup page.
    Clients are not blocked.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.user.is_staff:
            # Allow access to service_settings page and static/media files
            path = request.path
            if not any(path.startswith(p) for p in ["/settings/services/", "/static/", "/media/"]):
                needs_setup = Service.objects.filter(is_active=True, duration_minutes__isnull=True).exists()
                if needs_setup:
                    # Use absolute path to avoid reverse() failures if route name changes
                    messages.warning(request, "Set service durations before using the system.")
                    return HttpResponseRedirect("/settings/services/")
        return self.get_response(request)
