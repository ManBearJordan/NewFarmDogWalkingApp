from django.http import HttpResponse
from django.views.decorators.http import require_safe
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


@require_safe
def health_check(request):
    """
    Simple health endpoint for uptime checks/tunnel verification.
    """
    return HttpResponse("OK", content_type="text/plain", status=200)


@login_required
def calendar_smart_redirect(request):
    """
    Smart redirect for legacy /calendar/ URL.
    - Admin/staff users → /ops/calendar/
    - Client users → /portal/calendar/
    """
    user = request.user
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return redirect("/ops/calendar/")
    return redirect("/portal/calendar/")
