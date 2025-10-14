import os
from django.urls import path, include
from django.contrib import admin
from django.contrib.auth import views as auth_views

# Secret, env-driven admin URL. Keep the trailing slash.
# Set DJANGO_ADMIN_URL in .env, e.g.: DJANGO_ADMIN_URL=sk-hd7a4v0-admin/
ADMIN_URL = os.environ.get("DJANGO_ADMIN_URL", "django-admin/")

urlpatterns = [
    # Admin lives at a secret path only (env-driven)
    path(ADMIN_URL, admin.site.urls),
    # Login/Logout using built-in Django views
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='accounts_login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    # Include your app URLs after login; make sure their views require login OR rely on the middleware above
    path('', include('core.urls')),
]