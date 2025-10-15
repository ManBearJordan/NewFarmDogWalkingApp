"""
Tests for admin URL configuration via DJANGO_ADMIN_URL environment variable.
"""
import pytest
from django.test import Client
from django.contrib.auth.models import User
from django.conf import settings


@pytest.mark.django_db
def test_admin_url_setting_exists():
    """Test that DJANGO_ADMIN_URL setting is defined."""
    admin_url = getattr(settings, 'DJANGO_ADMIN_URL', None)
    assert admin_url is not None
    assert isinstance(admin_url, str)
    assert admin_url.endswith('/')


@pytest.mark.django_db
def test_admin_url_default_value():
    """Test that DJANGO_ADMIN_URL defaults to django-admin/."""
    admin_url = getattr(settings, 'DJANGO_ADMIN_URL', None)
    # Should be 'django-admin/' by default (unless overridden in .env)
    assert admin_url == 'django-admin/'


@pytest.mark.django_db
def test_admin_accessible_at_configured_url():
    """Test that admin is accessible at the configured URL."""
    admin_url = getattr(settings, 'DJANGO_ADMIN_URL', 'admin/')
    client = Client()
    
    # Try to access admin at the configured path
    resp = client.get(f'/{admin_url}')
    
    # Should redirect to login (302) or show login page (200)
    assert resp.status_code in (200, 302)


@pytest.mark.django_db
def test_admin_login_works_at_configured_url():
    """Test that admin login works at the configured URL."""
    admin_url = getattr(settings, 'DJANGO_ADMIN_URL', 'admin/')
    
    # Create a superuser
    User.objects.create_superuser(
        username="testadmin",
        password="testpass123",
        email="testadmin@test.com"
    )
    
    client = Client()
    
    # Login via the configured admin URL
    login_url = f'/{admin_url}login/'
    resp = client.post(login_url, {
        'username': 'testadmin',
        'password': 'testpass123',
        'next': f'/{admin_url}'
    })
    
    # Should redirect after successful login
    assert resp.status_code == 302


@pytest.mark.django_db
def test_admin_not_at_default_admin_path():
    """Test that /admin/ is not the admin path (we use secret URL)."""
    admin_url = getattr(settings, 'DJANGO_ADMIN_URL', 'admin/')
    
    # Only test if we're using a custom admin URL
    if admin_url != 'admin/':
        client = Client()
        
        # Try to access /admin/ - should not be the admin interface
        resp = client.get('/admin/')
        
        # Should either 404, or redirect somewhere else (via middleware)
        # But it shouldn't be the Django admin login
        assert resp.status_code in (302, 404)
