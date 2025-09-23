import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import Client

@pytest.fixture
def authed(client):
    u = User.objects.create_user(username="u", password="p")
    client.login(username="u", password="p")
    return client

@pytest.mark.django_db
def test_add_credit_updates_cents(authed):
    c = Client.objects.create(name="Alice", credit_cents=0)
    resp = authed.post(reverse("client_credit_add", args=[c.id]), {"amount": "2500"}, follow=True)
    assert resp.status_code == 200
    c.refresh_from_db()
    assert c.credit_cents == 2500

@pytest.mark.django_db
def test_stripe_link_via_email(authed, monkeypatch):
    c = Client.objects.create(name="Bob")
    from core import stripe_integration
    monkeypatch.setattr(stripe_integration, "ensure_customer", lambda client: "cus_TEST123")
    resp = authed.post(reverse("client_stripe_link", args=[c.id]), {"stripe_id_or_email": "bob@example.com"}, follow=True)
    assert resp.status_code == 200
    c.refresh_from_db()
    assert c.stripe_customer_id == "cus_TEST123"

@pytest.mark.django_db
def test_clients_stripe_sync_bulk(authed, monkeypatch):
    c1 = Client.objects.create(name="X", email="x@example.com")
    c2 = Client.objects.create(name="Y", email="")  # skipped (no email)
    calls = {"n": 0}
    from core import stripe_integration
    def fake_ensure(client):
        calls["n"] += 1
        return "cus_BULK"
    monkeypatch.setattr(stripe_integration, "ensure_customer", fake_ensure)
    resp = authed.post(reverse("clients_stripe_sync"), follow=True)
    assert resp.status_code == 200
    c1.refresh_from_db()
    c2.refresh_from_db()
    assert c1.stripe_customer_id == "cus_BULK"
    assert c2.stripe_customer_id in ("", None)
    assert calls["n"] == 1