import uuid
import threading
from django.utils.deprecation import MiddlewareMixin

_local = threading.local()

def get_request_id():
    return getattr(_local, "rid", None)

class RequestIDMiddleware(MiddlewareMixin):
    """
    Ensures each request gets a stable request id:
      - trusts inbound X-Request-ID if supplied
      - otherwise generates a uuid4 hex
    Makes it available to logging via a filter (see logging_filters.py).
    """
    def process_request(self, request):
        rid = request.META.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex
        _local.rid = rid
        request.request_id = rid

    def process_response(self, request, response):
        # cleanup per request to avoid thread leakage
        try:
            if hasattr(_local, "rid"):
                delattr(_local, "rid")
        except Exception:
            pass
        return response
