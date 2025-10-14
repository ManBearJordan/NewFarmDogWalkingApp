# newfarm/middleware.py
import os
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

class RedirectAnonymousToLoginMiddleware(MiddlewareMixin):
    """
    If the user is not authenticated, redirect to LOGIN_URL.
    Allowlist: admin, login, logout, password reset, static/media, health checks, etc.
    """
    ALLOW_PREFIXES = (
        '/static/', '/media/', '/healthz', '/readyz',
    )

    def process_request(self, request):
        path = request.path

        # allowlist by prefix
        if any(path.startswith(p) for p in self.ALLOW_PREFIXES):
            return None

        # allow Django admin (checks for both '/admin/' and the configured ADMIN_URL)
        admin_url = os.environ.get("DJANGO_ADMIN_URL", "django-admin/")
        if '/admin/' in path or path.startswith('/' + admin_url):
            return None

        # allow auth endpoints
        auth_allowed = [
            reverse('login'),
            '/accounts/login/',
            '/accounts/logout/',
            '/accounts/password_reset/',
        ]
        try:
            auth_allowed.append(reverse('logout'))
        except:
            pass
        
        if path in auth_allowed:
            return None

        # already authenticated? let them pass
        if request.user.is_authenticated:
            return None

        # otherwise, bounce to login
        return redirect(f"{reverse('login')}?next={path}")
