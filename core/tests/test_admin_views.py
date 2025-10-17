import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.test import Client


@pytest.mark.django_db
def test_admin_stripe_status_basic():
    """Test basic access to stripe status page (requires staff)"""
    user = User.objects.create_user(username="user", password="p", is_staff=True)
    client = Client()
    client.login(username="user", password="p")
    
    resp = client.get(reverse("stripe_status"))
    assert resp.status_code == 200
    # Check for key status elements
    assert b"key_status" in resp.content or b"Stripe" in resp.content


@pytest.mark.django_db 
def test_stripe_key_update_post():
    """Test POST request to update stripe key"""
    user = User.objects.create_user(username="user", password="p", is_staff=True)
    client = Client()
    client.login(username="user", password="p")
    
    resp = client.post(reverse("stripe_key_update"), {
        "stripe_api_key": "sk_test_newkey123"
    })
    # Should redirect back to stripe_status
    assert resp.status_code == 302


@pytest.mark.django_db
def test_stripe_status_refresh():
    """Test stripe status page with refresh parameter"""  
    user = User.objects.create_user(username="user", password="p", is_staff=True)
    client = Client()
    client.login(username="user", password="p")
    
    resp = client.get(reverse("stripe_status") + "?refresh=1")
    assert resp.status_code == 200