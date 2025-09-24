import pytest
from django.urls import reverse
from django.contrib.auth.models import User

@pytest.mark.django_db
def test_portal_confirm_handles_missing_invoice_url(client):
    # Create and login a user first
    user = User.objects.create_user(username="testuser", password="testpass")
    client.login(username="testuser", password="testpass")
    
    # Simulate the session state written by portal_booking_create
    session = client.session
    session["portal_confirm"] = {
        "booking_id": 123,
        "service": "Dog Walk",
        "start": "2025-09-24T09:00:00+10:00",
        "end": "2025-09-24T10:00:00+10:00",
        "due": True,
        "invoice_url": None,  # hosted link not ready yet
    }
    session.save()
    resp = client.get(reverse("portal_booking_confirm"))
    assert resp.status_code == 200
    html = resp.content.decode().lower()
    assert "a payment is due" in html
    # The placeholder message from the template should appear
    assert "link isn't available yet" in html or "link isn't available yet" in html