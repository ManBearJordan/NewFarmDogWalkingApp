import pytest
from django.urls import reverse
from django.contrib.auth.models import User

@pytest.mark.django_db
def test_client_list_requires_auth(client):
    # Test that client_list redirects anonymous users to login
    resp = client.get(reverse("client_list"))
    assert resp.status_code == 302
    assert '/login' in resp.url or 'accounts/login' in resp.url

@pytest.mark.django_db 
def test_client_list_authenticated(client):
    # Test that staff users can access client_list
    user = User.objects.create_user(username="testuser", password="testpass", is_staff=True)
    client.login(username="testuser", password="testpass")
    resp = client.get(reverse("client_list"))
    assert resp.status_code == 200