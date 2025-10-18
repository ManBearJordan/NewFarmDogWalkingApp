from django.shortcuts import redirect
from django.urls import reverse
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
            allowed = {reverse('service_settings')}
            path = request.path
            if not any(path.startswith(p) for p in allowed.union({"/static/", "/media/"})):
                if Service.objects.filter(is_active=True, duration_minutes__isnull=True).exists():
                    messages.warning(request, "Set service durations before using the system.")
                    return redirect('service_settings')
        return self.get_response(request)
