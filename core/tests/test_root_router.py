"""
Tests for the root_router function in newfarm/urls.py
"""
import pytest
from django.test import Client
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.mark.django_db
def test_root_redirects_unauthenticated_to_login():
    """Test that unauthenticated users are redirected to login."""
    client = Client()
    resp = client.get('/')
    
    # Should redirect to login
    assert resp.status_code == 302
    assert resp.url == '/accounts/login/'


@pytest.mark.django_db
def test_root_redirects_authenticated_to_portal():
    """Test that authenticated users are redirected to portal."""
    client = Client()
    
    # Create and login a regular user
    User.objects.create_user(username='testuser', password='testpass')
    client.login(username='testuser', password='testpass')
    
    resp = client.get('/')
    
    # Should redirect to portal
    assert resp.status_code == 302
    assert resp.url == '/portal/'


@pytest.mark.django_db
def test_root_redirects_staff_to_portal():
    """Test that staff users are also redirected to portal."""
    client = Client()
    
    # Create and login a staff user
    User.objects.create_user(username='staffuser', password='testpass', is_staff=True)
    client.login(username='staffuser', password='testpass')
    
    resp = client.get('/')
    
    # Should redirect to portal (they can use menu to reach /bookings/)
    assert resp.status_code == 302
    assert resp.url == '/portal/'


@pytest.mark.django_db
def test_root_url_name():
    """Test that the root URL has the correct name."""
    url = reverse('root')
    assert url == '/'
