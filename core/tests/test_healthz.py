import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_healthz_endpoint_accessible(client):
    """Test that /healthz endpoint is accessible without authentication."""
    resp = client.get(reverse("healthz"))
    assert resp.status_code == 200
    assert resp.content == b"OK"
    assert resp['content-type'] == "text/plain"

@pytest.mark.django_db
def test_healthz_endpoint_get_only(client):
    """Test that /healthz only accepts GET requests."""
    resp = client.post(reverse("healthz"))
    assert resp.status_code == 405  # Method Not Allowed
