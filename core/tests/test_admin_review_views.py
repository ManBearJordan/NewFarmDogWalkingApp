from django.test import TestCase, Client as TestClient
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import datetime
from zoneinfo import ZoneInfo
from core.models import Booking, Client, Service

BRISBANE = ZoneInfo("Australia/Brisbane")


class AdminReviewViewsTests(TestCase):
    """Tests for admin review views."""

    def setUp(self):
        """Set up test data."""
        # Create staff user
        self.staff_user = User.objects.create_user(
            username='staff',
            password='testpass123',
            is_staff=True
        )
        
        # Create regular user
        self.regular_user = User.objects.create_user(
            username='regular',
            password='testpass123',
            is_staff=False
        )
        
        # Create client
        self.client_obj = Client.objects.create(
            name="Test Client",
            email="test@example.com",
            phone="1234567890"
        )
        
        # Create service
        self.service = Service.objects.create(
            code="walk30",
            name="30 Minute Walk",
            duration_minutes=30
        )
        
        # Create booking
        self.start_dt = datetime(2025, 10, 21, 10, 0, 0)
        self.end_dt = datetime(2025, 10, 21, 10, 30, 0)
        
        self.booking = Booking.objects.create(
            client=self.client_obj,
            service=self.service,
            service_code="walk30",
            service_name="30 Minute Walk",
            service_label="30 Minute Walk",
            start_dt=self.start_dt,
            end_dt=self.end_dt,
            location="Test Park",
            dogs=1,
            status="confirmed",
            price_cents=3000,
            requires_admin_review=True,
            review_diff={
                "dogs": {"booking": 1, "invoice": 2},
                "location": {"booking": "Test Park", "invoice": "Different Park"}
            },
            review_source_invoice_id="in_test123"
        )
        
        self.test_client = TestClient()

    def test_review_list_requires_staff(self):
        """Review list should require staff login."""
        response = self.test_client.get(reverse('admin_review_list'), follow=True)
        # Should redirect to login
        self.assertIn('/login/', response.redirect_chain[-1][0])

    def test_review_list_regular_user_denied(self):
        """Regular users should not access review list."""
        self.test_client.login(username='regular', password='testpass123')
        response = self.test_client.get(reverse('admin_review_list'), follow=True)
        # Should redirect to login (staff_member_required)
        self.assertIn('/login/', response.redirect_chain[-1][0])

    def test_review_list_staff_access(self):
        """Staff users should access review list."""
        self.test_client.login(username='staff', password='testpass123')
        response = self.test_client.get(reverse('admin_review_list'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bookings Requiring Admin Review")
        self.assertContains(response, self.booking.client.name)

    def test_review_list_shows_bookings(self):
        """Review list should show bookings requiring review."""
        self.test_client.login(username='staff', password='testpass123')
        response = self.test_client.get(reverse('admin_review_list'), follow=True)
        self.assertContains(response, str(self.booking.id))
        self.assertContains(response, "in_test123")

    def test_review_list_empty(self):
        """Review list should handle no bookings needing review."""
        self.booking.requires_admin_review = False
        self.booking.save()
        
        self.test_client.login(username='staff', password='testpass123')
        response = self.test_client.get(reverse('admin_review_list'), follow=True)
        self.assertContains(response, "No bookings under review")

    def test_review_apply_requires_staff(self):
        """Review apply should require staff login."""
        response = self.test_client.get(
            reverse('admin_review_apply', kwargs={'booking_id': self.booking.id}),
            follow=True
        )
        self.assertIn('/login/', response.redirect_chain[-1][0])

    def test_review_apply_success(self):
        """Test applying review changes to booking."""
        self.test_client.login(username='staff', password='testpass123')
        response = self.test_client.post(
            reverse('admin_review_apply', kwargs={'booking_id': self.booking.id}),
            follow=True
        )
        
        # Should end up at review list after redirects
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(reverse('admin_review_list') in url for url, _ in response.redirect_chain))
        
        # Check booking was updated
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.dogs, 2)
        self.assertEqual(self.booking.location, "Different Park")
        self.assertFalse(self.booking.requires_admin_review)
        self.assertIsNone(self.booking.review_diff)
        self.assertIsNone(self.booking.review_source_invoice_id)

    def test_review_apply_datetime_fields(self):
        """Test applying datetime changes."""
        from django.utils import timezone as django_tz
        
        different_start = django_tz.make_aware(datetime(2025, 10, 21, 11, 0, 0), BRISBANE)
        different_end = django_tz.make_aware(datetime(2025, 10, 21, 11, 30, 0), BRISBANE)
        
        self.booking.review_diff = {
            "start_dt": {
                "booking": self.start_dt.isoformat(),
                "invoice": different_start.isoformat()
            },
            "end_dt": {
                "booking": self.end_dt.isoformat(),
                "invoice": different_end.isoformat()
            }
        }
        self.booking.save()
        
        self.test_client.login(username='staff', password='testpass123')
        self.test_client.post(
            reverse('admin_review_apply', kwargs={'booking_id': self.booking.id}),
            follow=True
        )
        
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.start_dt, different_start)
        self.assertEqual(self.booking.end_dt, different_end)

    def test_review_apply_service_code(self):
        """Test applying service code change."""
        # Create another service
        service2 = Service.objects.create(
            code="walk60",
            name="60 Minute Walk",
            duration_minutes=60
        )
        
        self.booking.review_diff = {
            "service_code": {
                "booking": "walk30",
                "invoice": "walk60"
            }
        }
        self.booking.save()
        
        self.test_client.login(username='staff', password='testpass123')
        self.test_client.post(
            reverse('admin_review_apply', kwargs={'booking_id': self.booking.id}),
            follow=True
        )
        
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.service.code, "walk60")

    def test_review_apply_nonexistent_booking(self):
        """Test applying review to non-existent booking."""
        self.test_client.login(username='staff', password='testpass123')
        response = self.test_client.post(
            reverse('admin_review_apply', kwargs={'booking_id': 99999}),
            follow=True
        )
        # Django's get_object_or_404 returns 404
        # The first redirect is SSL (301), then if it fails it should be 404
        self.assertEqual(response.status_code, 404)

    def test_review_dismiss_requires_staff(self):
        """Review dismiss should require staff login."""
        response = self.test_client.get(
            reverse('admin_review_dismiss', kwargs={'booking_id': self.booking.id}),
            follow=True
        )
        self.assertIn('/login/', response.redirect_chain[-1][0])

    def test_review_dismiss_success(self):
        """Test dismissing review without applying changes."""
        original_dogs = self.booking.dogs
        original_location = self.booking.location
        
        self.test_client.login(username='staff', password='testpass123')
        response = self.test_client.post(
            reverse('admin_review_dismiss', kwargs={'booking_id': self.booking.id}),
            follow=True
        )
        
        # Should end up at review list after redirects
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(reverse('admin_review_list') in url for url, _ in response.redirect_chain))
        
        # Check booking was NOT updated with invoice values
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.dogs, original_dogs)  # Should remain 1
        self.assertEqual(self.booking.location, original_location)  # Should remain "Test Park"
        
        # But review should be cleared
        self.assertFalse(self.booking.requires_admin_review)
        self.assertIsNone(self.booking.review_diff)
        self.assertIsNone(self.booking.review_source_invoice_id)

    def test_review_dismiss_nonexistent_booking(self):
        """Test dismissing review for non-existent booking."""
        self.test_client.login(username='staff', password='testpass123')
        response = self.test_client.post(
            reverse('admin_review_dismiss', kwargs={'booking_id': 99999}),
            follow=True
        )
        self.assertEqual(response.status_code, 404)

    def test_review_list_ordering(self):
        """Review list should order by start_dt descending."""
        # Create another booking with earlier date
        earlier_booking = Booking.objects.create(
            client=self.client_obj,
            service=self.service,
            service_code="walk30",
            service_name="30 Minute Walk",
            service_label="30 Minute Walk",
            start_dt=datetime(2025, 10, 20, 10, 0, 0),
            end_dt=datetime(2025, 10, 20, 10, 30, 0),
            location="Test Park",
            dogs=1,
            status="confirmed",
            price_cents=3000,
            requires_admin_review=True,
            review_diff={"dogs": {"booking": 1, "invoice": 2}},
            review_source_invoice_id="in_test456"
        )
        
        self.test_client.login(username='staff', password='testpass123')
        response = self.test_client.get(reverse('admin_review_list'), follow=True)
        
        # The later booking should appear first
        content = response.content.decode()
        # Find booking IDs in the table rows
        import re
        ids_in_order = re.findall(r'<td>(\d+)</td>', content)
        if len(ids_in_order) >= 2:
            # First should be the later booking (self.booking)
            self.assertEqual(int(ids_in_order[0]), self.booking.id)
            self.assertEqual(int(ids_in_order[1]), earlier_booking.id)
