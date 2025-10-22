import logging

class RequestIDLogFilter(logging.Filter):
    """
    Injects request_id into log records (or '-' if none).
    """
    def filter(self, record):
        rid = "-"
        try:
            from .middleware.request_id import get_request_id
            rid = get_request_id() or "-"
        except Exception:
            pass
        record.request_id = rid
        return True
