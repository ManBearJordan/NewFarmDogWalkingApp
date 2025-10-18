import json
from django.test import TestCase, Client as TestClient
from django.utils import timezone
from core.models import Client, Booking


class BookingPaymentStatusTestCase(TestCase):
    """Test payment status tracking on Booking model."""

    def setUp(self):
        self.client = Client.objects.create(
            name="Test Client",
            email="test@example.com",
            phone="1234567890",
            address="123 Test St",
            status="active",
        )
        self.booking = Booking.objects.create(
            client=self.client,
            service_code="walk",
            service_name="Dog Walk",
            service_label="Standard Walk",
            start_dt=timezone.now(),
            end_dt=timezone.now() + timezone.timedelta(hours=1),
            location="Park",
            status="confirmed",
            price_cents=5000,
            stripe_invoice_id="inv_test123",
        )

    def test_booking_default_payment_status(self):
        """New bookings should have unpaid status by default."""
        self.assertEqual(self.booking.payment_status, 'unpaid')
        self.assertIsNone(self.booking.paid_at)
        self.assertIsNone(self.booking.invoice_pdf_url)

    def test_mark_paid_method(self):
        """Test the mark_paid() method."""
        self.booking.mark_paid()
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.payment_status, 'paid')
        self.assertIsNotNone(self.booking.paid_at)

    def test_mark_paid_with_custom_time(self):
        """Test mark_paid() with custom timestamp."""
        custom_time = timezone.now() - timezone.timedelta(days=1)
        self.booking.mark_paid(when=custom_time)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.payment_status, 'paid')
        self.assertEqual(self.booking.paid_at, custom_time)


class WebhookInvoiceEventsTestCase(TestCase):
    """Test webhook handling for invoice events."""

    def setUp(self):
        self.test_client = TestClient()
        self.client = Client.objects.create(
            name="Test Client",
            email="test@example.com",
            phone="1234567890",
            address="123 Test St",
            status="active",
            stripe_customer_id="cus_test123",
        )
        self.booking = Booking.objects.create(
            client=self.client,
            service_code="walk",
            service_name="Dog Walk",
            service_label="Standard Walk",
            start_dt=timezone.now(),
            end_dt=timezone.now() + timezone.timedelta(hours=1),
            location="Park",
            status="confirmed",
            price_cents=5000,
            stripe_invoice_id="inv_test123",
        )

    def test_invoice_finalized_event(self):
        """Test invoice.finalized webhook sets PDF URL."""
        event_data = {
            "type": "invoice.finalized",
            "data": {
                "object": {
                    "id": "inv_test123",
                    "invoice_pdf": "https://example.com/invoice.pdf",
                }
            }
        }
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(event_data),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.invoice_pdf_url, "https://example.com/invoice.pdf")
        self.assertEqual(self.booking.payment_status, 'unpaid')  # Still unpaid

    def test_invoice_payment_succeeded_event(self):
        """Test invoice.payment_succeeded webhook marks as paid."""
        event_data = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": "inv_test123",
                    "hosted_invoice_url": "https://example.com/invoice",
                }
            }
        }
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(event_data),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.payment_status, 'paid')
        self.assertIsNotNone(self.booking.paid_at)
        self.assertEqual(self.booking.invoice_pdf_url, "https://example.com/invoice")

    def test_invoice_voided_event(self):
        """Test invoice.voided webhook marks as void."""
        event_data = {
            "type": "invoice.voided",
            "data": {
                "object": {
                    "id": "inv_test123",
                }
            }
        }
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(event_data),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.payment_status, 'void')

    def test_invoice_payment_failed_event(self):
        """Test invoice.payment_failed webhook marks as failed."""
        event_data = {
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "id": "inv_test123",
                }
            }
        }
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(event_data),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.payment_status, 'failed')

    def test_invoice_event_no_matching_booking(self):
        """Test invoice event with non-existent invoice ID."""
        event_data = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": "inv_nonexistent",
                }
            }
        }
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(event_data),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)  # Should still return OK

    def test_invoice_payment_succeeded_preserves_paid_at(self):
        """Test that paid_at is not overwritten if already set."""
        original_time = timezone.now() - timezone.timedelta(days=1)
        self.booking.paid_at = original_time
        self.booking.save()
        
        event_data = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": "inv_test123",
                }
            }
        }
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(event_data),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.payment_status, 'paid')
        self.assertEqual(self.booking.paid_at, original_time)  # Not overwritten
