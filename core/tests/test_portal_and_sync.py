import os
from django.test import TestCase, Client as WebClient, override_settings
from django.contrib.auth.models import User
from core.models import Service
from core.subscription_sync import sync_subscriptions_to_bookings_and_calendar

class PortalAndSyncTests(TestCase):
    def setUp(self):
        self.web = WebClient()
        self.staff = User.objects.create_user("staff", "s@example.com", "x")
        self.staff.is_staff = True
        self.staff.save()
        self.user = User.objects.create_user("client", "c@example.com", "x")

    def test_client_portal_requires_login(self):
        resp = self.web.get("/portal/")
        self.assertEqual(resp.status_code, 302)  # redirect to login
        self.web.login(username="client", password="x")
        resp = self.web.get("/portal/")
        # Not linked client is handled gracefully (no 500)
        self.assertNotEqual(resp.status_code, 500)

    def test_service_duration_guard_redirects_staff(self):
        # active service with no duration triggers redirect
        Service.objects.create(code="walk30", name="Walk 30", is_active=True, duration_minutes=None)
        self.web.login(username="staff", password="x")
        resp = self.web.get("/portal/")
        # redirected to settings path until durations are set
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/settings/services/", resp["Location"])

    @override_settings(PRODUCTION=False)
    def test_sync_without_stripe_key_in_nonprod_is_safe(self):
        # ensure env keys absent
        os.environ.pop("STRIPE_SECRET_KEY", None)
        os.environ.pop("STRIPE_API_KEY", None)
        result = sync_subscriptions_to_bookings_and_calendar(horizon_days=1)
        # Should not raise; returns a dict with error count
        self.assertIsInstance(result, dict)
        self.assertIn('errors', result)
