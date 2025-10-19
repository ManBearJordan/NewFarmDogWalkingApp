from django.http import HttpResponse
from django.views.decorators.http import require_safe

@require_safe
def health_check(request):
    """
    Simple health endpoint for uptime checks/tunnel verification.
    """
    return HttpResponse("OK", content_type="text/plain", status=200)
