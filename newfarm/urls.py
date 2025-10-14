import os
from django.urls import path, include
from django.contrib import admin

# Secret, env-driven admin URL. Keep the trailing slash.
# Set DJANGO_ADMIN_URL in .env, e.g.: DJANGO_ADMIN_URL=sk-hd7a4v0-admin/
ADMIN_URL = os.environ.get("DJANGO_ADMIN_URL", "django-admin/")

urlpatterns = [
    # Public site at root via your core app
    path("", include("core.urls")),

    # Admin lives at a secret path only (env-driven)
    path(ADMIN_URL, admin.site.urls),
]