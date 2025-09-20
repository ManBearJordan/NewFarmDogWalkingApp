from django.urls import path, include
from django.contrib import admin
from core import admin_views

urlpatterns = [
    path('admin/stripe/', admin_views.stripe_status_view, name='stripe_status'),
    path('admin/stripe/diagnostics/', admin_views.stripe_diagnostics_view, name='stripe_diagnostics'),
    path('admin/', admin.site.urls),
    path('', lambda r: None),
]