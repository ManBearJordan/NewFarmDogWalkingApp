import pytest
from django.urls import reverse
from django.contrib.auth.models import User

@pytest.mark.django_db
def test_client_list_allows_anonymous(client):
    # Test that client_list allows anonymous access
    resp = client.get(reverse("client_list"))
    assert resp.status_code == 200

@pytest.mark.django_db 
def test_client_list_authenticated(client):
    # Test that authenticated users can access client_list
    user = User.objects.create_user(username="testuser", password="testpass")
    client.login(username="testuser", password="testpass")
    resp = client.get(reverse("client_list"))
    assert resp.status_code == 200