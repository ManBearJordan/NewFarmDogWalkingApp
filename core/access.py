"""
Access control decorators for views.
Provides robust access guards that prevent redirect loops by returning 403 pages
instead of redirecting when access is denied.
"""
from functools import wraps
from django.conf import settings
from django.shortcuts import redirect, render
from django.contrib.auth import REDIRECT_FIELD_NAME


def _login_redirect(request):
    """Helper to redirect to login with next parameter."""
    next_q = f"?{REDIRECT_FIELD_NAME}={request.get_full_path()}"
    return redirect(f"{settings.LOGIN_URL}{next_q}")


def require_superuser(view):
    """
    Decorator: require superuser access.
    - If not authenticated: redirect to login
    - If not superuser: return 403 page (no redirect to prevent loops)
    """
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        u = request.user
        if not u.is_authenticated:
            return _login_redirect(request)
        if not getattr(u, "is_superuser", False):
            # Important: DO NOT redirect (prevents loops). Return 403 page.
            return render(request, "403.html", status=403)
        return view(request, *args, **kwargs)
    return _wrapped


def get_user_client(user):
    """
    Helper to get the client linked to this auth user.
    Returns Client or None.
    """
    from core.models import Client
    try:
        return Client.objects.get(user=user)
    except Client.DoesNotExist:
        return None


def require_client(view):
    """
    Decorator: require authenticated user with linked Client record.
    - If not authenticated: redirect to login
    - If missing client profile: return 403 page with hint (no redirect to prevent loops)
    """
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        u = request.user
        if not u.is_authenticated:
            return _login_redirect(request)
        client = None
        try:
            client = get_user_client(u)
        except Exception:
            client = None
        if not client:
            return render(
                request,
                "403.html",
                {"message": "Your login isn't linked to a client record yet."},
                status=403
            )
        # Store client in request for convenience
        request._nfdw_client = client
        return view(request, *args, **kwargs)
    return _wrapped
