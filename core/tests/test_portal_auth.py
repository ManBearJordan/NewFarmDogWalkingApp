import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from zoneinfo import ZoneInfo
from core.models import Client, Booking

TZ = ZoneInfo("Australia/Brisbane")

@pytest.mark.django_db
def test_portal_requires_login(client):
    resp = client.get(reverse("portal_home"))
    # Redirect to login
    assert resp.status_code in (302, 301)
    assert reverse("login") in resp.url

@pytest.mark.django_db
def test_portal_lists_only_users_client_bookings(client):
    # Create two clients and two users
    u1 = User.objects.create_user(username="alice", password="p")
    u2 = User.objects.create_user(username="bob", password="p")
    c1 = Client.objects.create(name="Alice Client", email="alice@test.com", phone="123", address="123 Test St", status="active", user=u1)
    c2 = Client.objects.create(name="Bob Client", email="bob@test.com", phone="456", address="456 Test St", status="active", user=u2)
    
    # Create future bookings (tomorrow) to ensure they show up
    now = timezone.now().astimezone(TZ)
    tomorrow = now + timezone.timedelta(days=1)
    
    # Two bookings, one for each client
    b1 = Booking.objects.create(
        client=c1, service_code="walk", service_name="Dog Walking", service_label="Walk", 
        start_dt=tomorrow, end_dt=tomorrow + timezone.timedelta(hours=1), 
        location="Park", status="confirmed"
    )
    b2 = Booking.objects.create(
        client=c2, service_code="walk", service_name="Dog Walking", service_label="Walk", 
        start_dt=tomorrow, end_dt=tomorrow + timezone.timedelta(hours=1), 
        location="Park", status="confirmed"
    )
    
    # Login as alice
    client.login(username="alice", password="p")
    html = client.get(reverse("portal_home")).content.decode()
    # Look for unique identifiers that would be associated with bookings in the table
    assert "Alice Client" in html  # The client name should appear
    assert "Bob Client" not in html  # The other client's name should NOT appear
    # Also check that we don't see "No upcoming bookings"
    assert "No upcoming bookings" not in html

@pytest.mark.django_db
def test_portal_handles_user_without_client(client):
    u = User.objects.create_user(username="nouser", password="p")
    client.login(username="nouser", password="p")
    html = client.get(reverse("portal_home")).content.decode()
    assert "not linked to a client profile" in html.lower()