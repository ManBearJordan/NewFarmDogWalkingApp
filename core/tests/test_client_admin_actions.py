"""Tests for client admin actions (disable/remove login)."""
import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory
from core.models import Client
from core.admin import ClientAdmin
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage


@pytest.mark.django_db
def test_disable_portal_login_action():
    """Test disabling portal login for clients."""
    # Create a user and client
    user = User.objects.create_user(username="testuser", password="testpass")
    client = Client.objects.create(
        name="Test Client",
        email="test@test.com",
        phone="123",
        address="addr",
        status="active",
        user=user
    )
    
    # Verify user is active
    assert user.is_active is True
    
    # Create admin instance and proper request
    admin = ClientAdmin(Client, AdminSite())
    factory = RequestFactory()
    request = factory.get('/admin/')
    request.session = {}
    request._messages = FallbackStorage(request)
    
    # Call the action
    queryset = Client.objects.filter(id=client.id)
    admin.disable_portal_login(request, queryset)
    
    # Verify user is now inactive
    user.refresh_from_db()
    assert user.is_active is False


@pytest.mark.django_db
def test_remove_portal_login_action():
    """Test removing portal login for clients."""
    # Create a user and client
    user = User.objects.create_user(username="testuser2", password="testpass")
    client = Client.objects.create(
        name="Test Client 2",
        email="test2@test.com",
        phone="123",
        address="addr",
        status="active",
        user=user
    )
    
    # Verify user is linked
    assert client.user is not None
    
    # Create admin instance and proper request
    admin = ClientAdmin(Client, AdminSite())
    factory = RequestFactory()
    request = factory.get('/admin/')
    request.session = {}
    request._messages = FallbackStorage(request)
    
    # Call the action
    queryset = Client.objects.filter(id=client.id)
    admin.remove_portal_login(request, queryset)
    
    # Verify user is unlinked
    client.refresh_from_db()
    assert client.user is None


@pytest.mark.django_db
def test_can_self_reschedule_field():
    """Test that can_self_reschedule field works correctly."""
    client = Client.objects.create(
        name="Test Client",
        email="test@test.com",
        phone="123",
        address="addr",
        status="active",
        can_self_reschedule=True
    )
    
    assert client.can_self_reschedule is True
    
    client.can_self_reschedule = False
    client.save()
    client.refresh_from_db()
    
    assert client.can_self_reschedule is False
