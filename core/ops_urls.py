# core/ops_urls.py
from django.urls import path
from django.views.generic import RedirectView

urlpatterns = [
    # Default /ops/ -> bookings
    path("", RedirectView.as_view(url="/ops/bookings/", permanent=False), name="ops_root"),

    # Map each staff section under /ops/ to the existing route
    path("bookings/",      RedirectView.as_view(url="/bookings/", permanent=False), name="ops_bookings"),
    path("calendar/",      RedirectView.as_view(url="/calendar/", permanent=False), name="ops_calendar"),
    path("subscriptions/", RedirectView.as_view(url="/subscriptions/", permanent=False), name="ops_subscriptions"),
    path("clients/",       RedirectView.as_view(url="/clients/", permanent=False), name="ops_clients"),
    path("pets/",          RedirectView.as_view(url="/pets/", permanent=False), name="ops_pets"),
    path("tags/",          RedirectView.as_view(url="/tags/", permanent=False), name="ops_tags"),

    # Optional: tools index if you have it
    path("tools/",         RedirectView.as_view(url="/admin-tools/", permanent=False), name="ops_tools"),
]
