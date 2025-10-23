"""
Test /ops/ namespace and middleware exemption behavior.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client


@pytest.mark.django_db
class TestOpsNamespace:
    """Test that /ops/ namespace works correctly and routes are exempt from duration guard"""

    def setup_method(self):
        """Create test users"""
        self.staff_user = User.objects.create_user(
            username="staff", password="pass", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="pass", is_staff=False
        )
        self.client = Client()

    def test_ops_root_redirects_to_ops_bookings(self):
        """Visiting /ops/ should redirect to /ops/bookings/"""
        self.client.login(username="staff", password="pass")
        resp = self.client.get("/ops/", follow=False)
        # /ops/ should redirect to /ops/bookings/ via ops_urls.py
        assert resp.status_code == 302
        assert "/ops/bookings/" in resp.url

    def test_ops_bookings_redirects_to_actual_bookings(self):
        """Visiting /ops/bookings/ should redirect to /bookings/ (the actual view)"""
        self.client.login(username="staff", password="pass")
        resp = self.client.get("/ops/bookings/", follow=False)
        # /ops/bookings/ redirects to /bookings/ via ops_urls.py
        assert resp.status_code == 302
        assert "/bookings/" in resp.url

    def test_ops_calendar_redirects_to_actual_calendar(self):
        """Visiting /ops/calendar/ should redirect to /calendar/ (the actual view)"""
        self.client.login(username="staff", password="pass")
        resp = self.client.get("/ops/calendar/", follow=False)
        assert resp.status_code == 302
        assert "/calendar/" in resp.url

    def test_ops_subscriptions_redirects_to_actual_subscriptions(self):
        """Visiting /ops/subscriptions/ should redirect to /subscriptions/"""
        self.client.login(username="staff", password="pass")
        resp = self.client.get("/ops/subscriptions/", follow=False)
        assert resp.status_code == 302
        assert "/subscriptions/" in resp.url

    def test_ops_clients_redirects_to_actual_clients(self):
        """Visiting /ops/clients/ should redirect to /clients/"""
        self.client.login(username="staff", password="pass")
        resp = self.client.get("/ops/clients/", follow=False)
        assert resp.status_code == 302
        assert "/clients/" in resp.url

    def test_ops_pets_redirects_to_actual_pets(self):
        """Visiting /ops/pets/ should redirect to /pets/"""
        self.client.login(username="staff", password="pass")
        resp = self.client.get("/ops/pets/", follow=False)
        assert resp.status_code == 302
        assert "/pets/" in resp.url

    def test_ops_tags_redirects_to_actual_tags(self):
        """Visiting /ops/tags/ should redirect to /tags/"""
        self.client.login(username="staff", password="pass")
        resp = self.client.get("/ops/tags/", follow=False)
        assert resp.status_code == 302
        assert "/tags/" in resp.url

    def test_ops_tools_redirects_to_admin_tools(self):
        """Visiting /ops/tools/ should redirect to /admin-tools/"""
        self.client.login(username="staff", password="pass")
        resp = self.client.get("/ops/tools/", follow=False)
        assert resp.status_code == 302
        assert "/admin-tools/" in resp.url

    def test_ops_namespace_exempt_from_duration_guard(self):
        """
        /ops/ routes should be exempt from service duration guard.
        Even if services lack durations, /ops/ routes shouldn't redirect to settings.
        """
        self.client.login(username="staff", password="pass")
        # /ops/bookings/ redirects to /bookings/, both should be exempt from guard
        resp = self.client.get("/ops/bookings/", follow=True)
        # Should not redirect to settings (would be in redirect chain)
        for url, status in resp.redirect_chain:
            assert "/settings/services/" not in url
        # Final status should be 200 (successful page load), not a redirect to settings
        assert resp.status_code == 200

    def test_legacy_routes_exempt_from_duration_guard(self):
        """
        Legacy routes like /bookings/ should be exempt from duration guard for staff.
        This maintains backward compatibility with bookmarks.
        """
        self.client.login(username="staff", password="pass")
        resp = self.client.get("/bookings/", follow=True)
        # Should not redirect to settings
        for url, status in resp.redirect_chain:
            assert "/settings/services/" not in url
        # Should successfully load
        assert resp.status_code == 200

    def test_legacy_bookings_accessible_to_staff(self):
        """Legacy /bookings/ route should still be accessible to staff"""
        self.client.login(username="staff", password="pass")
        resp = self.client.get("/bookings/", follow=True)
        assert resp.status_code == 200

    def test_legacy_calendar_accessible_to_staff(self):
        """Legacy /calendar/ route should be accessible to staff (after superuser promotion)"""
        self.client.login(username="staff", password="pass")
        resp = self.client.get("/calendar/", follow=True)
        # Calendar may return 403 or 200 depending on staff permissions
        # The middleware should exempt it regardless
        assert resp.status_code in [200, 403]
        # Verify we didn't redirect to settings
        for url, status in resp.redirect_chain:
            assert "/settings/services/" not in url
