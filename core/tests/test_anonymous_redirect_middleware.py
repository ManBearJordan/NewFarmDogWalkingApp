"""Tests for the RedirectAnonymousToLoginMiddleware."""

import pytest
from django.test import RequestFactory, override_settings
from django.contrib.auth.models import User, AnonymousUser
from django.urls import reverse
from newfarm.middleware import RedirectAnonymousToLoginMiddleware


@pytest.fixture
def middleware():
    """Create middleware instance."""
    return RedirectAnonymousToLoginMiddleware(get_response=lambda r: None)


@pytest.fixture
def request_factory():
    """Create request factory."""
    return RequestFactory()


@pytest.fixture
def authenticated_user(db):
    """Create an authenticated user."""
    return User.objects.create_user(username='testuser', password='testpass')


@pytest.mark.django_db
class TestRedirectAnonymousToLoginMiddleware:
    """Test the middleware that redirects anonymous users to login."""

    def test_static_files_allowed_without_auth(self, middleware, request_factory):
        """Test that static files are accessible without authentication."""
        request = request_factory.get('/static/test.css')
        request.user = AnonymousUser()
        response = middleware(request)
        assert response is None  # Allow through

    def test_media_files_allowed_without_auth(self, middleware, request_factory):
        """Test that media files are accessible without authentication."""
        request = request_factory.get('/media/test.jpg')
        request.user = AnonymousUser()
        response = middleware(request)
        assert response is None  # Allow through

    def test_admin_allowed_without_middleware_redirect(self, middleware, request_factory):
        """Test that admin URLs bypass the middleware (Django admin has its own auth)."""
        request = request_factory.get('/django-admin/')
        request.user = AnonymousUser()
        response = middleware(request)
        assert response is None  # Allow through (admin handles its own auth)

    def test_authenticated_user_allowed(self, middleware, request_factory, authenticated_user):
        """Test that authenticated users can access any path."""
        request = request_factory.get('/portal/')
        request.user = authenticated_user
        response = middleware(request)
        assert response is None  # Allow through

    def test_anonymous_user_redirected_to_login(self, middleware, request_factory):
        """Test that anonymous users are redirected to login for protected paths."""
        request = request_factory.get('/portal/')
        request.user = AnonymousUser()
        response = middleware(request)
        assert response is not None
        assert response.status_code == 302
        assert '/portal/' in response.url  # Should include next parameter

    def test_healthz_allowed_without_auth(self, middleware, request_factory):
        """Test that health check endpoints are accessible without authentication."""
        request = request_factory.get('/healthz')
        request.user = AnonymousUser()
        response = middleware(request)
        assert response is None  # Allow through

    def test_readyz_allowed_without_auth(self, middleware, request_factory):
        """Test that readiness check endpoints are accessible without authentication."""
        request = request_factory.get('/readyz')
        request.user = AnonymousUser()
        response = middleware(request)
        assert response is None  # Allow through
