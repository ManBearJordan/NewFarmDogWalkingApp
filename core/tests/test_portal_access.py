import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import Client

@pytest.mark.django_db
def test_admin_pages_not_visible_to_client_user(client):
    # Client user logs in but cannot access admin pages
    u = User.objects.create_user(username="cli", password="p")
    Client.objects.create(name="X", user=u)
    client.login(username="cli", password="p")
    # Example: stripe status page - should redirect non-staff users
    resp = client.get(reverse("stripe_status"))
    # Non-staff should be redirected
    assert resp.status_code in [302, 403]

@pytest.mark.django_db
def test_portal_requires_linked_client(client):
    u = User.objects.create_user(username="nouser", password="p")
    client.login(username="nouser", password="p")
    resp = client.get(reverse("portal_home"))
    assert resp.status_code == 200
    assert b"not linked to a client profile" in resp.content.lower()

@pytest.mark.django_db
def test_stripe_key_update_post(client):
    """Test POST to stripe key update endpoint"""
    u = User.objects.create_user(username="admin", password="p", is_staff=True)
    client.login(username="admin", password="p")
    
    resp = client.post(reverse("stripe_key_update"), {
        "stripe_api_key": "sk_test_newkey123"
    })
    assert resp.status_code == 302  # Should redirect

@pytest.mark.django_db
def test_stripe_diagnostics_view(client):
    """Test stripe diagnostics JSON endpoint"""
    u = User.objects.create_user(username="admin", password="p", is_staff=True)
    client.login(username="admin", password="p")
    
    resp = client.get(reverse("stripe_diagnostics"))
    assert resp.status_code == 200
    # Should return JSON