"""
Treat requests as HTTPS when behind Cloudflare Tunnel even if X-Forwarded-Proto
is missing, by honoring CF-Visitor header when it declares 'scheme:https'.
This helps SecurityMiddleware and request.is_secure() behave correctly.
"""
import json
from django.utils.deprecation import MiddlewareMixin


class CloudflareProtoMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Respect standard proxy header if present
        xf_proto = request.META.get("HTTP_X_FORWARDED_PROTO")
        if xf_proto:
            return
        # Fall back to CF-Visitor
        cfv = request.META.get("HTTP_CF_VISITOR")
        if not cfv:
            return
        try:
            data = json.loads(cfv)
        except Exception:
            data = {}
        if data.get("scheme") == "https":
            # Emulate SECURE_PROXY_SSL_HEADER outcome so is_secure() is True
            request.META["HTTP_X_FORWARDED_PROTO"] = "https"
