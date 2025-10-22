import pytest
from django.test import RequestFactory
from django.http import HttpResponse
from core.middleware.request_id import RequestIDMiddleware, get_request_id


@pytest.mark.django_db
class TestRequestIDMiddleware:
    """Test the RequestIDMiddleware"""

    def setup_method(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.middleware = RequestIDMiddleware(lambda request: HttpResponse("OK"))

    def test_generates_request_id(self):
        """Test that middleware generates a request ID"""
        request = self.factory.get("/")
        
        response = self.middleware(request)
        
        assert hasattr(request, "request_id")
        assert request.request_id is not None
        assert len(request.request_id) == 32  # uuid4.hex is 32 chars

    def test_uses_inbound_request_id(self):
        """Test that middleware uses inbound X-Request-ID header"""
        custom_id = "custom-request-id-12345"
        request = self.factory.get("/", HTTP_X_REQUEST_ID=custom_id)
        
        response = self.middleware(request)
        
        assert request.request_id == custom_id

    def test_cleans_up_thread_local(self):
        """Test that middleware cleans up thread local storage"""
        request = self.factory.get("/")
        
        # Before processing
        assert get_request_id() is None
        
        # Process request (sets thread local)
        self.middleware.process_request(request)
        assert get_request_id() is not None
        
        # Process response (cleans up)
        response = HttpResponse("OK")
        self.middleware.process_response(request, response)
        assert get_request_id() is None

    def test_request_id_available_during_request(self):
        """Test that request ID is available via get_request_id during request"""
        request = self.factory.get("/")
        
        def get_response(request):
            # This simulates the view being called during request processing
            current_id = get_request_id()
            assert current_id is not None
            assert current_id == request.request_id
            return HttpResponse("OK")
        
        middleware = RequestIDMiddleware(get_response)
        response = middleware(request)
        
        # After response, should be cleaned up
        assert get_request_id() is None
