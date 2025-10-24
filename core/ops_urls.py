# core/ops_urls.py
# This file is deprecated - /ops/ routes are now defined directly in core/urls.py
# with proper access guards. Keeping this file empty to avoid import errors.
from django.urls import path

urlpatterns = [
    # All /ops/ routes are now in core/urls.py with require_superuser guards
]
