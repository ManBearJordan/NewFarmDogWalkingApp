from django.test import TestCase, Client as TestClient
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch, MagicMock
from core.models import Booking, Client, Service, StripeSubscriptionLink, StripeSubscriptionSchedule

BRISBANE = ZoneInfo("Australia/Brisbane")


class AdminInvoiceMetadataViewTests(TestCase):
    """Tests for admin invoice metadata view."""

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
            phone="1234567890",
            address="123 Test St",
            status="active"
        )
        
        # Create service
        self.service = Service.objects.create(
            code="walk30",
            name="30 Minute Walk",
            duration_minutes=30
        )
        
        # Create booking with invoice ID
        self.start_dt = datetime(2025, 10, 21, 10, 0, 0, tzinfo=BRISBANE)
        self.end_dt = datetime(2025, 10, 21, 10, 30, 0, tzinfo=BRISBANE)
        
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
            stripe_invoice_id="in_test123",
            requires_admin_review=True,
            review_diff={
                "dogs": {"booking": 1, "invoice": 2},
                "location": {"booking": "Test Park", "invoice": "Different Park"}
            }
        )
        
        self.test_client = TestClient()

    def test_invoice_metadata_requires_staff(self):
        """Invoice metadata view should require staff login."""
        response = self.test_client.get(
            reverse('admin_invoice_metadata', kwargs={'booking_id': self.booking.id}),
            follow=True
        )
        # Should redirect to login
        self.assertIn('/login/', response.redirect_chain[-1][0])

    def test_invoice_metadata_regular_user_denied(self):
        """Regular users should not access invoice metadata."""
        self.test_client.login(username='regular', password='testpass123')
        response = self.test_client.get(
            reverse('admin_invoice_metadata', kwargs={'booking_id': self.booking.id}),
            follow=True
        )
        # Should redirect to login (staff_member_required)
        self.assertIn('/login/', response.redirect_chain[-1][0])

    def test_invoice_metadata_staff_access(self):
        """Staff users should access invoice metadata."""
        self.test_client.login(username='staff', password='testpass123')
        response = self.test_client.get(
            reverse('admin_invoice_metadata', kwargs={'booking_id': self.booking.id}),
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Booking #{self.booking.id}")
        self.assertContains(response, self.booking.client.name)

    def test_invoice_metadata_no_invoice_id(self):
        """View should handle booking without invoice ID."""
        booking_no_invoice = Booking.objects.create(
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
            stripe_invoice_id=None
        )
        
        self.test_client.login(username='staff', password='testpass123')
        response = self.test_client.get(
            reverse('admin_invoice_metadata', kwargs={'booking_id': booking_no_invoice.id}),
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no Stripe invoice id attached")

    @patch('stripe.Invoice.retrieve')
    def test_invoice_metadata_with_stripe_data(self, mock_retrieve):
        """View should display Stripe invoice data."""
        # Mock Stripe invoice response
        mock_line_item = MagicMock()
        mock_line_item.description = "Walk service"
        mock_line_item.amount = 3000
        mock_line_item.metadata = {
            "booking_id": str(self.booking.id),
            "booking_start": self.start_dt.isoformat(),
            "booking_end": self.end_dt.isoformat(),
            "dogs": "2",
            "location": "Different Park",
            "service_code": "walk30"
        }
        
        mock_invoice = MagicMock()
        mock_invoice.lines.data = [mock_line_item]
        mock_retrieve.return_value = mock_invoice
        
        self.test_client.login(username='staff', password='testpass123')
        response = self.test_client.get(
            reverse('admin_invoice_metadata', kwargs={'booking_id': self.booking.id}),
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Walk service")
        self.assertContains(response, "Differences vs Booking")

    @patch('stripe.Invoice.retrieve')
    def test_invoice_metadata_stripe_error(self, mock_retrieve):
        """View should handle Stripe API errors gracefully."""
        mock_retrieve.side_effect = Exception("Stripe API error")
        
        self.test_client.login(username='staff', password='testpass123')
        response = self.test_client.get(
            reverse('admin_invoice_metadata', kwargs={'booking_id': self.booking.id}),
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Could not fetch invoice")

    def test_invoice_metadata_nonexistent_booking(self):
        """View should return 404 for non-existent booking."""
        self.test_client.login(username='staff', password='testpass123')
        response = self.test_client.get(
            reverse('admin_invoice_metadata', kwargs={'booking_id': 99999}),
            follow=True
        )
        self.assertEqual(response.status_code, 404)

    def test_invoice_metadata_shows_review_diff(self):
        """View should display review diff when present."""
        self.test_client.login(username='staff', password='testpass123')
        response = self.test_client.get(
            reverse('admin_invoice_metadata', kwargs={'booking_id': self.booking.id}),
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Current Review Differences")
        self.assertContains(response, "Under review")

    def test_invoice_metadata_with_subscription_schedule(self):
        """View should display subscription schedule when available."""
        # Create subscription link and schedule
        sub_link = StripeSubscriptionLink.objects.create(
            stripe_subscription_id="sub_test123",
            client=self.client_obj,
            service_code=self.service.code,
            status="active",
            active=True
        )
        
        sched = StripeSubscriptionSchedule.objects.create(
            sub=sub_link,
            weekdays_csv="mon,wed,fri",
            default_time="10:30",
            days="MON,WED,FRI",
            start_time="10:30",
            location="Test Park",
            repeats="weekly"
        )
        
        self.test_client.login(username='staff', password='testpass123')
        response = self.test_client.get(
            reverse('admin_invoice_metadata', kwargs={'booking_id': self.booking.id}),
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Subscription Schedule")
        self.assertContains(response, "Weekly")
        self.assertContains(response, "MON,WED,FRI")

    def test_invoice_metadata_no_subscription_schedule(self):
        """View should handle absence of subscription schedule."""
        self.test_client.login(username='staff', password='testpass123')
        response = self.test_client.get(
            reverse('admin_invoice_metadata', kwargs={'booking_id': self.booking.id}),
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No active schedule record found")

    @patch('stripe.Invoice.retrieve')
    def test_invoice_metadata_filters_by_booking_id(self, mock_retrieve):
        """View should only show line items for the current booking."""
        # Mock invoice with multiple line items
        mock_line_item1 = MagicMock()
        mock_line_item1.description = "Other booking"
        mock_line_item1.amount = 2000
        mock_line_item1.metadata = {"booking_id": "999"}
        
        mock_line_item2 = MagicMock()
        mock_line_item2.description = "This booking"
        mock_line_item2.amount = 3000
        mock_line_item2.metadata = {"booking_id": str(self.booking.id)}
        
        mock_invoice = MagicMock()
        mock_invoice.lines.data = [mock_line_item1, mock_line_item2]
        mock_retrieve.return_value = mock_invoice
        
        self.test_client.login(username='staff', password='testpass123')
        response = self.test_client.get(
            reverse('admin_invoice_metadata', kwargs={'booking_id': self.booking.id}),
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This booking")
        self.assertNotContains(response, "Other booking")


class BookingAdminMethodsTests(TestCase):
    """Tests for BookingAdmin display methods."""

    def setUp(self):
        """Set up test data."""
        self.client_obj = Client.objects.create(
            name="Test Client",
            email="test2@example.com",
            phone="1234567890",
            address="123 Test St",
            status="active"
        )
        
        self.service = Service.objects.create(
            code="walk60",
            name="60 Minute Walk",
            duration_minutes=60
        )
        
        self.booking = Booking.objects.create(
            client=self.client_obj,
            service=self.service,
            service_code="walk60",
            service_name="60 Minute Walk",
            service_label="60 Minute Walk",
            start_dt=datetime(2025, 10, 21, 10, 0, 0, tzinfo=BRISBANE),
            end_dt=datetime(2025, 10, 21, 11, 0, 0, tzinfo=BRISBANE),
            location="Test Park",
            dogs=1,
            status="confirmed",
            price_cents=5000,
            stripe_invoice_id="in_test456"
        )
        
        from core.admin import BookingAdmin
        self.admin = BookingAdmin(Booking, None)

    def test_review_flag_no_review(self):
        """Review flag should show dash when no review needed."""
        self.booking.requires_admin_review = False
        self.booking.save()
        
        result = self.admin.review_flag(self.booking)
        self.assertEqual(result, "—")

    def test_review_flag_under_review(self):
        """Review flag should show warning when under review."""
        self.booking.requires_admin_review = True
        self.booking.save()
        
        result = self.admin.review_flag(self.booking)
        self.assertEqual(result, "⚠️")

    def test_review_summary_no_diff(self):
        """Review summary should show dash when no diff."""
        self.booking.review_diff = None
        self.booking.save()
        
        result = self.admin.review_summary(self.booking)
        self.assertEqual(result, "—")

    def test_review_summary_with_diff(self):
        """Review summary should show changed keys."""
        self.booking.review_diff = {
            "dogs": {"booking": 1, "invoice": 2},
            "location": {"booking": "Park A", "invoice": "Park B"}
        }
        self.booking.save()
        
        result = self.admin.review_summary(self.booking)
        # Should show comma-separated sorted keys
        self.assertIn("dogs", result)
        self.assertIn("location", result)

    def test_invoice_meta_link_no_invoice(self):
        """Invoice meta link should show dash when no invoice."""
        self.booking.stripe_invoice_id = None
        self.booking.save()
        
        result = self.admin.invoice_meta_link(self.booking)
        self.assertEqual(result, "—")

    def test_invoice_meta_link_with_invoice(self):
        """Invoice meta link should show link when invoice exists."""
        result = self.admin.invoice_meta_link(self.booking)
        self.assertIn('<a href=', result)
        self.assertIn('Invoice metadata</a>', result)
        self.assertIn(str(self.booking.id), result)
