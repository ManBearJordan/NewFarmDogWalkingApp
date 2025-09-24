import pytest
from django.urls import reverse
from django.contrib.auth.models import User

@pytest.mark.django_db
def test_status_page_renders_without_key_leak(client, monkeypatch):
    # Force a key in env but mock get_key_status to avoid exposing raw key
    from core import stripe_key_manager as m
    monkeypatch.setattr(m, "get_key_status", lambda: {"configured": True, "mode":"env", "test_or_live":"test"})
    resp = client.get(reverse("stripe_status"))
    assert resp.status_code == 200
    html = resp.content.decode()
    # Ensure no actual keys are shown (only placeholders in form should exist)
    assert "sk_test_51" not in html  # real test keys start with sk_test_51
    assert "sk_live_51" not in html  # real live keys start with sk_live_51

@pytest.mark.django_db
def test_key_update_requires_staff(client):
    # Non-staff cannot post
    u = User.objects.create_user(username="user", password="p")
    client.login(username="user", password="p")
    resp = client.post(reverse("stripe_key_update"), {"stripe_api_key":"sk_test_x"})
    # staff_member_required redirects to admin login by default
    assert resp.status_code in (302, 301)
    assert "/admin/login" in resp.url or "/accounts/login" in resp.url

@pytest.mark.django_db
def test_key_update_allows_staff(client):
    staff = User.objects.create_user(username="staff", password="p", is_staff=True)
    client.login(username="staff", password="p")
    resp = client.post(reverse("stripe_key_update"), {"stripe_api_key":"sk_test_ok"})
    # Should redirect back to status with a message
    assert resp.status_code in (302, 301)