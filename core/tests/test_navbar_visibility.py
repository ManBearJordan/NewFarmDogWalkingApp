"""
Test navbar visibility based on user authentication and staff status.
Ensures staff-only links are hidden from regular authenticated users.
"""
import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.test import Client


@pytest.mark.django_db
class TestNavbarVisibility:
    """Test that navbar links are properly shown/hidden based on user type"""

    def setup_method(self):
        """Create test users"""
        from core.models import Client as ClientModel
        
        self.staff_user = User.objects.create_user(
            username="staff", password="pass", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="pass", is_staff=False
        )
        # Create a client profile for the regular user so they can access portal pages
        self.client_profile = ClientModel.objects.create(
            name="Test Client",
            email="regular@example.com",
            phone="1234567890",
            address="Test Address",
            status="active",
            user=self.regular_user
        )
        self.client = Client()

    def test_calendar_link_visible_to_all_authenticated_users(self):
        """Calendar link should be visible to all authenticated users"""
        # Regular user should see calendar link
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("calendar_legacy"), follow=True)
        assert resp.status_code == 200
        assert b'Calendar' in resp.content or b'calendar' in resp.content
        
        # Staff user should also see calendar link
        self.client.login(username="staff", password="pass")
        resp = self.client.get(reverse("calendar_legacy"), follow=True)
        assert resp.status_code == 200

    def test_bookings_link_hidden_from_regular_users(self):
        """Bookings link should only be visible to staff users"""
        # Regular user viewing calendar should NOT see bookings link in navbar
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("calendar_legacy"), follow=True)
        assert resp.status_code == 200
        # The navbar should not contain a link to booking_list for regular users
        # We check that the booking_list URL is not in the response
        booking_url = reverse("booking_list")
        assert booking_url.encode() not in resp.content or b'Bookings</a>' not in resp.content

    def test_bookings_link_visible_to_staff(self):
        """Bookings link should be visible to staff users"""
        self.client.login(username="staff", password="pass")
        resp = self.client.get(reverse("calendar_legacy"), follow=True)
        assert resp.status_code == 200
        # Staff should see the Bookings link
        assert b'Bookings</a>' in resp.content

    def test_admin_dropdown_hidden_from_regular_users(self):
        """Admin dropdown should only be visible to staff users"""
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("calendar_legacy"), follow=True)
        assert resp.status_code == 200
        # Regular users should not see the Admin dropdown
        assert b'Admin</a>' not in resp.content or b'adminMenu' not in resp.content

    def test_admin_dropdown_visible_to_staff(self):
        """Admin dropdown should be visible to staff users"""
        self.client.login(username="staff", password="pass")
        resp = self.client.get(reverse("calendar_legacy"), follow=True)
        assert resp.status_code == 200
        # Staff should see the Admin dropdown
        assert b'Admin</a>' in resp.content or b'adminMenu' in resp.content

    def test_clients_link_hidden_from_regular_users(self):
        """Clients link should only be visible to staff users"""
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("calendar_legacy"), follow=True)
        assert resp.status_code == 200
        # Regular users should not see Clients link
        clients_url = reverse("client_list")
        assert clients_url.encode() not in resp.content or b'Clients</a>' not in resp.content

    def test_subscriptions_link_hidden_from_regular_users(self):
        """Subscriptions link should only be visible to staff users"""
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("calendar_legacy"), follow=True)
        assert resp.status_code == 200
        # Regular users should not see Subscriptions link
        subs_url = reverse("subscriptions_list")
        assert subs_url.encode() not in resp.content or b'Subscriptions</a>' not in resp.content

    def test_anonymous_users_cannot_access_calendar(self):
        """Anonymous users should be redirected to login"""
        resp = self.client.get(reverse("calendar_legacy"))
        # Accept either 301 (HTTPS redirect) or 302 (login redirect)
        assert resp.status_code in [301, 302]
        # Follow redirects to ensure we end up at login
        resp = self.client.get(reverse("calendar_legacy"), follow=True)
        assert '/login' in resp.redirect_chain[-1][0] or 'accounts/login' in resp.redirect_chain[-1][0]
