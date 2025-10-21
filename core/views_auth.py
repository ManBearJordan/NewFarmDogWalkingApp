"""Authentication views for the core app."""

from django.contrib.auth import logout
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import RedirectView


class CustomLogoutView(RedirectView):
    """Logs out the user on GET or POST and redirects to login with a message."""
    url = reverse_lazy("login")

    def get(self, request, *args, **kwargs):
        logout(request)
        messages.success(request, "You've been logged out.")
        return super().get(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        """Support POST for backward compatibility with existing forms."""
        return self.get(request, *args, **kwargs)
