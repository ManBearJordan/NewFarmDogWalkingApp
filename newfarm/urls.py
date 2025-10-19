from django.urls import path, include, re_path
from django.contrib import admin
from django.conf import settings
from django.views.generic import RedirectView
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from core.views_misc import health_check

def root_router(request):
    if request.user.is_authenticated:
        # Clients land at portal; staff can use menu to reach /bookings/
        return HttpResponseRedirect('/portal/')
    return HttpResponseRedirect('/accounts/login/')

urlpatterns = [
    path('', root_router, name='root'),
    path('accounts/', include('django.contrib.auth.urls')),
    path(getattr(settings, 'DJANGO_ADMIN_URL', 'admin/'), admin.site.urls),
    path('', include('core.urls')),
    # Simple liveness probe
    path('healthz/', health_check, name='healthz'),
]