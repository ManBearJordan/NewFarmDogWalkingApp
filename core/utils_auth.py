from functools import wraps
from django.core.exceptions import PermissionDenied


def get_user_client_or_403(user):
    """
    Return the linked Client for this user or raise 403 if none.
    Use when a logged-in user must be a client.
    """
    # Expecting a OneToOne relation like user.client_profile
    client = getattr(user, "client_profile", None)
    if not client:
        raise PermissionDenied("No client profile.")
    return client


def require_client(view_func):
    """
    Decorator: requires authenticated user to have a linked Client profile.
    Pair with @login_required.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        _ = get_user_client_or_403(request.user)
        return view_func(request, *args, **kwargs)
    return _wrapped
