import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import Client
from unittest.mock import patch

@pytest.fixture
def authed(client):
    u = User.objects.create_user(username="u", password="p", is_staff=True)
    client.login(username="u", password="p")
    return client

@pytest.mark.django_db
def test_add_credit_updates_cents(authed):
    c = Client.objects.create(name="Alice", email="alice@test.com", phone="123", address="test address", status="active", credit_cents=0)
    resp = authed.post(reverse("client_credit_add", args=[c.id]), {"amount": "2500"}, follow=True)
    assert resp.status_code == 200
    c.refresh_from_db()
    assert c.credit_cents == 2500

@pytest.mark.django_db 
@patch('core.views.ensure_customer')
def test_stripe_link_via_email(mock_ensure, authed):
    c = Client.objects.create(name="Bob", email="", phone="123", address="test address", status="active")
    mock_ensure.return_value = "cus_TEST123"
    resp = authed.post(reverse("client_stripe_link", args=[c.id]), {"stripe_id_or_email": "bob@example.com"}, follow=True)
    assert resp.status_code == 200
    c.refresh_from_db()
    assert c.stripe_customer_id == "cus_TEST123"

@pytest.mark.django_db
@patch('core.views.ensure_customer')
def test_clients_stripe_sync_bulk(mock_ensure, authed):
    c1 = Client.objects.create(name="X", email="x@example.com", phone="123", address="test address", status="active")
    c2 = Client.objects.create(name="Y", email="", phone="123", address="test address", status="active")  # skipped (no email)
    mock_ensure.return_value = "cus_BULK"
    resp = authed.post(reverse("clients_stripe_sync"), follow=True)
    assert resp.status_code == 200
    c1.refresh_from_db()
    c2.refresh_from_db()
    assert c1.stripe_customer_id == "cus_BULK"
    assert c2.stripe_customer_id in ("", None)
    assert mock_ensure.call_count == 1  # Only called for c1 with email