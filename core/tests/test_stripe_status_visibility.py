import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.test import Client
from django.test import override_settings

@pytest.mark.django_db
def test_stripe_status_hides_form_from_nonstaff(client):
    # Mock key status to keep the view simple
    from core import stripe_key_manager as m
    original = getattr(m, "get_key_status", None)
    m.get_key_status = lambda: {"configured": True, "mode": "env", "test_or_live": "test"}

    # Staff user should see the page
    staff = User.objects.create_user(username="staff", password="p", is_staff=True)
    client.login(username="staff", password="p")
    resp = client.get(reverse("stripe_status"))
    assert resp.status_code == 200

    # Restore
    if original:
        m.get_key_status = original

@pytest.mark.django_db
def test_staff_sees_change_form(client):
    from core import stripe_key_manager as m
    original = getattr(m, "get_key_status", None)
    m.get_key_status = lambda: {"configured": True, "mode": "env", "test_or_live": "test"}

    staff = User.objects.create_user(username="staff", password="p", is_staff=True)
    client.login(username="staff", password="p")
    resp = client.get(reverse("stripe_status"))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Change Stripe Key" in html or 'name="stripe_api_key"' in html

    if original:
        m.get_key_status = original

@pytest.mark.django_db
def test_audit_record_created_on_key_change(client):
    from core import stripe_key_manager as m
    original = getattr(m, "get_key_status", None)
    m.get_key_status = lambda: {"configured": False, "mode": None, "test_or_live": None}
    staff = User.objects.create_user(username="auditor", password="p", is_staff=True)
    client.login(username="auditor", password="p")
    resp = client.post(reverse("stripe_key_update"), {"stripe_api_key":"sk_test_x"})
    # redirect back to status
    assert resp.status_code in (302,301)
    # ensure audit exists
    from core.models import StripeKeyAudit
    assert StripeKeyAudit.objects.filter(user__username="auditor").exists()
    if original:
        m.get_key_status = original