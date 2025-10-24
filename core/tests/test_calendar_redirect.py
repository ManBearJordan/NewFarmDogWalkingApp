"""
Tests for calendar smart redirect and /ops/ URL routing.
"""
from django.test import TestCase, Client as TestClient
from django.contrib.auth import get_user_model
from core.models import Client

User = get_user_model()


class CalendarSmartRedirectTests(TestCase):
    """Test the smart calendar redirect at /calendar/."""

    def setUp(self):
        self.client = TestClient()

    def test_unauthenticated_redirects_to_login(self):
        """Unauthenticated users should be redirected to login."""
        response = self.client.get('/calendar/')
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_superuser_redirects_to_ops_calendar(self):
        """Superusers should be redirected to /ops/calendar/."""
        user = User.objects.create_superuser(username='admin', password='pass')
        self.client.login(username='admin', password='pass')
        
        response = self.client.get('/calendar/')
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/ops/calendar/')

    def test_staff_redirects_to_ops_calendar(self):
        """Staff users should be redirected to /ops/calendar/."""
        user = User.objects.create_user(username='staff', password='pass')
        user.is_staff = True
        user.save()
        self.client.login(username='staff', password='pass')
        
        response = self.client.get('/calendar/')
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/ops/calendar/')

    def test_regular_user_redirects_to_portal_calendar(self):
        """Regular users should be redirected to /portal/calendar/."""
        user = User.objects.create_user(username='client', password='pass')
        self.client.login(username='client', password='pass')
        
        response = self.client.get('/calendar/')
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/portal/calendar/')


class OpsURLAccessTests(TestCase):
    """Test that /ops/ URLs are properly protected."""

    def setUp(self):
        self.client = TestClient()

    def test_ops_calendar_requires_superuser(self):
        """Non-superusers should get 403 at /ops/calendar/."""
        user = User.objects.create_user(username='regular', password='pass')
        self.client.login(username='regular', password='pass')
        
        response = self.client.get('/ops/calendar/')
        
        # Should return 403, not redirect (prevents loops)
        self.assertEqual(response.status_code, 403)

    def test_ops_calendar_allows_superuser(self):
        """Superusers should access /ops/calendar/."""
        user = User.objects.create_superuser(username='admin', password='pass')
        self.client.login(username='admin', password='pass')
        
        response = self.client.get('/ops/calendar/')
        
        # Should succeed (200) or redirect for additional requirements
        self.assertIn(response.status_code, [200, 302])

    def test_ops_bookings_requires_superuser(self):
        """Non-superusers should get 403 at /ops/bookings/."""
        user = User.objects.create_user(username='regular', password='pass')
        self.client.login(username='regular', password='pass')
        
        response = self.client.get('/ops/bookings/')
        
        self.assertEqual(response.status_code, 403)


class PortalURLAccessTests(TestCase):
    """Test that portal URLs require client profiles."""

    def setUp(self):
        self.client = TestClient()

    def test_portal_calendar_requires_client(self):
        """Users without client profile should get 403 at /portal/calendar/."""
        user = User.objects.create_user(username='noclient', password='pass')
        self.client.login(username='noclient', password='pass')
        
        response = self.client.get('/portal/calendar/')
        
        # Should return 403, not redirect (prevents loops)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "client record", status_code=403)

    def test_portal_calendar_allows_client(self):
        """Users with client profile should access /portal/calendar/."""
        user = User.objects.create_user(username='client', password='pass')
        client_obj = Client.objects.create(
            name='Test Client',
            email='test@example.com',
            phone='123456',
            address='Test Address',
            status='active',
            user=user
        )
        self.client.login(username='client', password='pass')
        
        response = self.client.get('/portal/calendar/')
        
        # Should succeed (200)
        self.assertEqual(response.status_code, 200)

    def test_portal_book_requires_client(self):
        """Users without client profile should get 403 at /portal/book/."""
        user = User.objects.create_user(username='noclient', password='pass')
        self.client.login(username='noclient', password='pass')
        
        response = self.client.get('/portal/book/')
        
        self.assertEqual(response.status_code, 403)
