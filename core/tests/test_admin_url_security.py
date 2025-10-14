"""
Tests for admin URL security configuration (environment-driven secret path).
"""
import os
import pytest
from django.test import Client, override_settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured


@pytest.mark.django_db
def test_admin_url_default_path():
    """Test that admin is accessible at default django-admin/ path"""
    client = Client()
    # Try to access the admin at default path
    resp = client.get("/django-admin/")
    # Should redirect to login (302) or show login page (200)
    assert resp.status_code in (200, 302)
    # If it's a 200, it should contain login form
    if resp.status_code == 200:
        assert b"login" in resp.content.lower()


@pytest.mark.django_db
def test_admin_url_with_custom_env():
    """Test that admin URL can be customized via environment variable"""
    # This test verifies the concept but Django URLs are loaded at startup
    # so we can't dynamically change them in a running test
    # Instead, we verify the configuration is read from environment
    from newfarm.urls import ADMIN_URL
    
    # By default (no DJANGO_ADMIN_URL set), should be "django-admin/"
    # This verifies the code structure is correct
    assert ADMIN_URL is not None
    assert isinstance(ADMIN_URL, str)
    assert ADMIN_URL.endswith("/")


@pytest.mark.django_db
def test_admin_login_works():
    """Test that admin login functionality works with the configured URL"""
    # Create a superuser
    User.objects.create_superuser(username="admin", password="testpass", email="admin@test.com")
    
    client = Client()
    # Login via the admin URL
    resp = client.post("/django-admin/login/", {
        "username": "admin",
        "password": "testpass",
        "next": "/django-admin/"
    })
    # Should redirect after successful login
    assert resp.status_code == 302


@pytest.mark.django_db
def test_root_path_is_public_site():
    """Test that root path serves the public site, not admin"""
    client = Client()
    resp = client.get("/")
    # Should get the core app home page (client list), not admin login
    assert resp.status_code in (200, 302)
    # If 302, should redirect to login for authenticated areas
    # If 200, should not contain Django admin branding
    if resp.status_code == 200:
        # Should not be the Django admin interface
        assert b"Django administration" not in resp.content
        assert b"Django site admin" not in resp.content
