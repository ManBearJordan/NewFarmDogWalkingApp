import pytest
from django.test import RequestFactory
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from core.middleware.service_duration import ServiceDurationGuardMiddleware
from core.models import Service


@pytest.mark.django_db
class TestServiceDurationGuardMiddleware:
    """Test the ServiceDurationGuardMiddleware with staff portal exemptions"""

    def setup_method(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.middleware = ServiceDurationGuardMiddleware(lambda request: HttpResponse("OK"))
        
        # Create a staff user
        self.staff_user = User.objects.create_user(
            username="staff", password="password", is_staff=True
        )
        
        # Create a regular user
        self.client_user = User.objects.create_user(
            username="client", password="password", is_staff=False
        )

    def add_session_and_messages(self, request):
        """Add session and messages support to a request"""
        # Add session
        session_middleware = SessionMiddleware(lambda x: x)
        session_middleware.process_request(request)
        request.session.save()
        
        # Add messages
        message_middleware = MessageMiddleware(lambda x: x)
        message_middleware.process_request(request)
        return request

    def test_non_staff_not_blocked(self):
        """Test that non-staff users are never blocked"""
        # Create a service without duration
        Service.objects.create(code="WALK", name="Dog Walk", is_active=True, duration_minutes=None)
        
        request = self.factory.get("/bookings/")
        request.user = self.client_user
        request = self.add_session_and_messages(request)
        
        response = self.middleware(request)
        
        assert response.status_code == 200
        assert response.content == b"OK"

    def test_staff_allowed_on_django_admin_paths(self):
        """Test that staff users can access Django admin paths without redirect"""
        # Create a service without duration
        Service.objects.create(code="WALK", name="Dog Walk", is_active=True, duration_minutes=None)
        
        # Test default admin path
        request = self.factory.get("/admin/")
        request.user = self.staff_user
        request = self.add_session_and_messages(request)
        
        response = self.middleware(request)
        
        assert response.status_code == 200
        assert response.content == b"OK"

    def test_staff_allowed_on_bookings_path(self):
        """Test that staff users can access /bookings/ path without redirect"""
        # Create a service without duration
        Service.objects.create(code="WALK", name="Dog Walk", is_active=True, duration_minutes=None)
        
        request = self.factory.get("/bookings/")
        request.user = self.staff_user
        request = self.add_session_and_messages(request)
        
        response = self.middleware(request)
        
        assert response.status_code == 200
        assert response.content == b"OK"

    def test_staff_allowed_on_ops_bookings_path(self):
        """Test that staff users can access /ops/bookings/ path without redirect"""
        # Create a service without duration
        Service.objects.create(code="WALK", name="Dog Walk", is_active=True, duration_minutes=None)
        
        request = self.factory.get("/ops/bookings/")
        request.user = self.staff_user
        request = self.add_session_and_messages(request)
        
        response = self.middleware(request)
        
        assert response.status_code == 200
        assert response.content == b"OK"

    def test_staff_allowed_on_calendar_path(self):
        """Test that staff users can access /calendar/ path without redirect"""
        # Create a service without duration
        Service.objects.create(code="WALK", name="Dog Walk", is_active=True, duration_minutes=None)
        
        request = self.factory.get("/calendar/")
        request.user = self.staff_user
        request = self.add_session_and_messages(request)
        
        response = self.middleware(request)
        
        assert response.status_code == 200
        assert response.content == b"OK"

    def test_staff_allowed_on_ops_calendar_path(self):
        """Test that staff users can access /ops/calendar/ path without redirect"""
        # Create a service without duration
        Service.objects.create(code="WALK", name="Dog Walk", is_active=True, duration_minutes=None)
        
        request = self.factory.get("/ops/calendar/")
        request.user = self.staff_user
        request = self.add_session_and_messages(request)
        
        response = self.middleware(request)
        
        assert response.status_code == 200
        assert response.content == b"OK"

    def test_staff_allowed_on_subscriptions_path(self):
        """Test that staff users can access /subscriptions/ path without redirect"""
        # Create a service without duration
        Service.objects.create(code="WALK", name="Dog Walk", is_active=True, duration_minutes=None)
        
        request = self.factory.get("/subscriptions/")
        request.user = self.staff_user
        request = self.add_session_and_messages(request)
        
        response = self.middleware(request)
        
        assert response.status_code == 200
        assert response.content == b"OK"

    def test_staff_allowed_on_ops_subscriptions_path(self):
        """Test that staff users can access /ops/subscriptions/ path without redirect"""
        # Create a service without duration
        Service.objects.create(code="WALK", name="Dog Walk", is_active=True, duration_minutes=None)
        
        request = self.factory.get("/ops/subscriptions/")
        request.user = self.staff_user
        request = self.add_session_and_messages(request)
        
        response = self.middleware(request)
        
        assert response.status_code == 200
        assert response.content == b"OK"

    def test_staff_allowed_on_clients_path(self):
        """Test that staff users can access /clients/ path without redirect"""
        # Create a service without duration
        Service.objects.create(code="WALK", name="Dog Walk", is_active=True, duration_minutes=None)
        
        request = self.factory.get("/clients/")
        request.user = self.staff_user
        request = self.add_session_and_messages(request)
        
        response = self.middleware(request)
        
        assert response.status_code == 200
        assert response.content == b"OK"

    def test_staff_allowed_on_pets_path(self):
        """Test that staff users can access /pets/ path without redirect"""
        # Create a service without duration
        Service.objects.create(code="WALK", name="Dog Walk", is_active=True, duration_minutes=None)
        
        request = self.factory.get("/pets/")
        request.user = self.staff_user
        request = self.add_session_and_messages(request)
        
        response = self.middleware(request)
        
        assert response.status_code == 200
        assert response.content == b"OK"

    def test_staff_allowed_on_tags_path(self):
        """Test that staff users can access /tags/ path without redirect"""
        # Create a service without duration
        Service.objects.create(code="WALK", name="Dog Walk", is_active=True, duration_minutes=None)
        
        request = self.factory.get("/tags/")
        request.user = self.staff_user
        request = self.add_session_and_messages(request)
        
        response = self.middleware(request)
        
        assert response.status_code == 200
        assert response.content == b"OK"

    def test_staff_allowed_on_service_settings_path(self):
        """Test that staff users can access /settings/services/ path without redirect"""
        # Create a service without duration
        Service.objects.create(code="WALK", name="Dog Walk", is_active=True, duration_minutes=None)
        
        request = self.factory.get("/settings/services/")
        request.user = self.staff_user
        request = self.add_session_and_messages(request)
        
        response = self.middleware(request)
        
        assert response.status_code == 200
        assert response.content == b"OK"

    def test_staff_redirected_on_other_paths_without_duration(self):
        """Test that staff users are redirected on non-exempt paths when service lacks duration"""
        # Create a service without duration
        Service.objects.create(code="WALK", name="Dog Walk", is_active=True, duration_minutes=None)
        
        request = self.factory.get("/some/other/path/")
        request.user = self.staff_user
        request = self.add_session_and_messages(request)
        
        response = self.middleware(request)
        
        assert response.status_code == 302
        assert response.url == "/settings/services/"

    def test_staff_not_redirected_when_all_services_have_duration(self):
        """Test that staff users are not redirected when all active services have duration"""
        # Create a service with duration
        Service.objects.create(code="WALK", name="Dog Walk", is_active=True, duration_minutes=30)
        
        request = self.factory.get("/some/other/path/")
        request.user = self.staff_user
        request = self.add_session_and_messages(request)
        
        response = self.middleware(request)
        
        assert response.status_code == 200
        assert response.content == b"OK"

    def test_staff_not_blocked_by_inactive_service_without_duration(self):
        """Test that staff users are not blocked by inactive services without duration"""
        # Create an inactive service without duration
        Service.objects.create(code="WALK", name="Dog Walk", is_active=False, duration_minutes=None)
        
        request = self.factory.get("/some/other/path/")
        request.user = self.staff_user
        request = self.add_session_and_messages(request)
        
        response = self.middleware(request)
        
        assert response.status_code == 200
        assert response.content == b"OK"

    def test_staff_allowed_on_static_path(self):
        """Test that staff users can access /static/ path without redirect"""
        # Create a service without duration
        Service.objects.create(code="WALK", name="Dog Walk", is_active=True, duration_minutes=None)
        
        request = self.factory.get("/static/css/portal.css")
        request.user = self.staff_user
        request = self.add_session_and_messages(request)
        
        response = self.middleware(request)
        
        assert response.status_code == 200
        assert response.content == b"OK"

    def test_staff_allowed_on_media_path(self):
        """Test that staff users can access /media/ path without redirect"""
        # Create a service without duration
        Service.objects.create(code="WALK", name="Dog Walk", is_active=True, duration_minutes=None)
        
        request = self.factory.get("/media/uploads/image.jpg")
        request.user = self.staff_user
        request = self.add_session_and_messages(request)
        
        response = self.middleware(request)
        
        assert response.status_code == 200
        assert response.content == b"OK"
