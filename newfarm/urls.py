from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.views.generic import RedirectView

urlpatterns = [
    # Secret admin path from .env (DJANGO_ADMIN_URL=sk-hd7a4v0-admin/)
    path(getattr(settings, 'DJANGO_ADMIN_URL', 'admin/'), admin.site.urls),

    # Customer auth/portal
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('core.urls')),
]