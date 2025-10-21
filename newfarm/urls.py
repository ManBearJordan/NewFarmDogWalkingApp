from django.urls import path, include, re_path
from django.contrib import admin
from django.conf import settings
from django.views.generic import RedirectView
from django.contrib.auth.decorators import login_required

urlpatterns = [
    path(getattr(settings, 'DJANGO_ADMIN_URL', 'admin/'), admin.site.urls),
    path('', include('core.urls')),
]