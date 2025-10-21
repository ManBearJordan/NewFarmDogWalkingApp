# Middleware module
# Import middleware classes for backward compatibility
from .service_duration import ServiceDurationGuardMiddleware

__all__ = ['ServiceDurationGuardMiddleware']
