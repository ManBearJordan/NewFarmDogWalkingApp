from django.test import TestCase
from datetime import datetime
from zoneinfo import ZoneInfo
from core.models import Booking, Client, Service
from core.invoice_validation import validate_invoice_against_bookings, _parse_iso_local


BRISBANE = ZoneInfo("Australia/Brisbane")


class InvoiceValidationTests(TestCase):
    """Tests for invoice validation against bookings."""

    def setUp(self):
        """Set up test data."""
        self.client = Client.objects.create(
            name="Test Client",
            email="test@example.com",
            phone="1234567890"
        )
        self.service = Service.objects.create(
            code="walk30",
            name="30 Minute Walk",
            duration_minutes=30
        )
        # Create a naive datetime in Brisbane timezone
        self.start_dt = datetime(2025, 10, 21, 10, 0, 0)
        self.end_dt = datetime(2025, 10, 21, 10, 30, 0)
        
        self.booking = Booking.objects.create(
            client=self.client,
            service=self.service,
            service_code="walk30",
            service_name="30 Minute Walk",
            service_label="30 Minute Walk",
            start_dt=self.start_dt,
            end_dt=self.end_dt,
            location="Test Park",
            dogs=1,
            status="confirmed",
            price_cents=3000
        )

    def test_parse_iso_local_with_z_suffix(self):
        """Test parsing ISO datetime with Z suffix."""
        # 10:00 Brisbane time = 00:00 UTC (AEST is UTC+10)
        dt_str = "2025-10-21T00:00:00Z"
        result = _parse_iso_local(dt_str)
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 10)
        self.assertEqual(result.day, 21)
        self.assertEqual(result.hour, 10)  # Converted to Brisbane time

    def test_parse_iso_local_with_offset(self):
        """Test parsing ISO datetime with timezone offset."""
        dt_str = "2025-10-21T10:00:00+10:00"
        result = _parse_iso_local(dt_str)
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 10)
        self.assertEqual(result.day, 21)
        self.assertEqual(result.hour, 10)

    def test_parse_iso_local_naive(self):
        """Test parsing naive ISO datetime (assumed Brisbane)."""
        dt_str = "2025-10-21T10:00:00"
        result = _parse_iso_local(dt_str)
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 10)
        self.assertEqual(result.day, 21)
        self.assertEqual(result.hour, 10)

    def test_parse_iso_local_invalid(self):
        """Test parsing invalid datetime string."""
        result = _parse_iso_local("invalid")
        self.assertIsNone(result)

    def test_parse_iso_local_empty(self):
        """Test parsing empty string."""
        result = _parse_iso_local("")
        self.assertIsNone(result)

    def test_no_validation_without_metadata(self):
        """Invoice without metadata shouldn't flag bookings."""
        invoice = {
            "id": "in_test123",
            "lines": {
                "data": [
                    {"metadata": {}}
                ]
            }
        }
        validate_invoice_against_bookings(invoice)
        self.booking.refresh_from_db()
        self.assertFalse(self.booking.requires_admin_review)

    def test_no_validation_without_booking_id(self):
        """Invoice without booking_id shouldn't flag bookings."""
        invoice = {
            "id": "in_test123",
            "lines": {
                "data": [
                    {"metadata": {"some_key": "some_value"}}
                ]
            }
        }
        validate_invoice_against_bookings(invoice)
        self.booking.refresh_from_db()
        self.assertFalse(self.booking.requires_admin_review)

    def test_matching_metadata_no_review(self):
        """Matching metadata shouldn't flag booking for review."""
        invoice = {
            "id": "in_test123",
            "lines": {
                "data": [
                    {
                        "metadata": {
                            "booking_id": str(self.booking.id),
                            "booking_start": self.start_dt.isoformat(),
                            "booking_end": self.end_dt.isoformat(),
                            "dogs": "1",
                            "location": "Test Park",
                            "service_code": "walk30"
                        }
                    }
                ]
            }
        }
        validate_invoice_against_bookings(invoice)
        self.booking.refresh_from_db()
        self.assertFalse(self.booking.requires_admin_review)

    def test_mismatched_start_time(self):
        """Mismatched start time should flag booking for review."""
        different_start = datetime(2025, 10, 21, 11, 0, 0)
        invoice = {
            "id": "in_test123",
            "lines": {
                "data": [
                    {
                        "metadata": {
                            "booking_id": str(self.booking.id),
                            "booking_start": different_start.isoformat(),
                            "booking_end": self.end_dt.isoformat(),
                        }
                    }
                ]
            }
        }
        validate_invoice_against_bookings(invoice)
        self.booking.refresh_from_db()
        self.assertTrue(self.booking.requires_admin_review)
        self.assertIn("start_dt", self.booking.review_diff)
        self.assertEqual(self.booking.review_source_invoice_id, "in_test123")

    def test_mismatched_end_time(self):
        """Mismatched end time should flag booking for review."""
        different_end = datetime(2025, 10, 21, 11, 30, 0)
        invoice = {
            "id": "in_test123",
            "lines": {
                "data": [
                    {
                        "metadata": {
                            "booking_id": str(self.booking.id),
                            "booking_start": self.start_dt.isoformat(),
                            "booking_end": different_end.isoformat(),
                        }
                    }
                ]
            }
        }
        validate_invoice_against_bookings(invoice)
        self.booking.refresh_from_db()
        self.assertTrue(self.booking.requires_admin_review)
        self.assertIn("end_dt", self.booking.review_diff)

    def test_mismatched_dogs(self):
        """Mismatched dogs count should flag booking for review."""
        invoice = {
            "id": "in_test123",
            "lines": {
                "data": [
                    {
                        "metadata": {
                            "booking_id": str(self.booking.id),
                            "dogs": "2",
                        }
                    }
                ]
            }
        }
        validate_invoice_against_bookings(invoice)
        self.booking.refresh_from_db()
        self.assertTrue(self.booking.requires_admin_review)
        self.assertIn("dogs", self.booking.review_diff)
        self.assertEqual(self.booking.review_diff["dogs"]["booking"], 1)
        self.assertEqual(self.booking.review_diff["dogs"]["invoice"], 2)

    def test_mismatched_location(self):
        """Mismatched location should flag booking for review."""
        invoice = {
            "id": "in_test123",
            "lines": {
                "data": [
                    {
                        "metadata": {
                            "booking_id": str(self.booking.id),
                            "location": "Different Park",
                        }
                    }
                ]
            }
        }
        validate_invoice_against_bookings(invoice)
        self.booking.refresh_from_db()
        self.assertTrue(self.booking.requires_admin_review)
        self.assertIn("location", self.booking.review_diff)
        self.assertEqual(self.booking.review_diff["location"]["booking"], "Test Park")
        self.assertEqual(self.booking.review_diff["location"]["invoice"], "Different Park")

    def test_mismatched_service_code(self):
        """Mismatched service code should flag booking for review."""
        invoice = {
            "id": "in_test123",
            "lines": {
                "data": [
                    {
                        "metadata": {
                            "booking_id": str(self.booking.id),
                            "service_code": "walk60",
                        }
                    }
                ]
            }
        }
        validate_invoice_against_bookings(invoice)
        self.booking.refresh_from_db()
        self.assertTrue(self.booking.requires_admin_review)
        self.assertIn("service_code", self.booking.review_diff)
        self.assertEqual(self.booking.review_diff["service_code"]["booking"], "walk30")
        self.assertEqual(self.booking.review_diff["service_code"]["invoice"], "walk60")

    def test_multiple_mismatches(self):
        """Multiple mismatches should all be recorded in diff."""
        invoice = {
            "id": "in_test123",
            "lines": {
                "data": [
                    {
                        "metadata": {
                            "booking_id": str(self.booking.id),
                            "dogs": "2",
                            "location": "Different Park",
                            "service_code": "walk60",
                        }
                    }
                ]
            }
        }
        validate_invoice_against_bookings(invoice)
        self.booking.refresh_from_db()
        self.assertTrue(self.booking.requires_admin_review)
        self.assertIn("dogs", self.booking.review_diff)
        self.assertIn("location", self.booking.review_diff)
        self.assertIn("service_code", self.booking.review_diff)

    def test_nonexistent_booking_id(self):
        """Invoice with non-existent booking_id shouldn't crash."""
        invoice = {
            "id": "in_test123",
            "lines": {
                "data": [
                    {
                        "metadata": {
                            "booking_id": "99999",
                            "dogs": "2",
                        }
                    }
                ]
            }
        }
        # Should not raise exception
        validate_invoice_against_bookings(invoice)

    def test_invalid_booking_id(self):
        """Invoice with invalid booking_id shouldn't crash."""
        invoice = {
            "id": "in_test123",
            "lines": {
                "data": [
                    {
                        "metadata": {
                            "booking_id": "not_a_number",
                            "dogs": "2",
                        }
                    }
                ]
            }
        }
        # Should not raise exception
        validate_invoice_against_bookings(invoice)

    def test_clear_review(self):
        """Test clear_review method resets review fields."""
        self.booking.requires_admin_review = True
        self.booking.review_diff = {"dogs": {"booking": 1, "invoice": 2}}
        self.booking.review_source_invoice_id = "in_test123"
        self.booking.save()
        
        self.booking.clear_review()
        self.booking.refresh_from_db()
        
        self.assertFalse(self.booking.requires_admin_review)
        self.assertIsNone(self.booking.review_diff)
        self.assertIsNone(self.booking.review_source_invoice_id)

    def test_stripe_object_format(self):
        """Test validation works with Stripe object format (attributes)."""
        # Simulate a Stripe object with attributes
        class MockInvoice:
            id = "in_test123"
            class Lines:
                data = [
                    type('obj', (object,), {
                        'metadata': {
                            'booking_id': str(self.booking.id),
                            'dogs': '2'
                        }
                    })()
                ]
            lines = Lines()
        
        invoice = MockInvoice()
        validate_invoice_against_bookings(invoice)
        self.booking.refresh_from_db()
        self.assertTrue(self.booking.requires_admin_review)
        self.assertIn("dogs", self.booking.review_diff)

    def test_multiple_line_items(self):
        """Test validation handles multiple line items."""
        # Create second booking
        booking2 = Booking.objects.create(
            client=self.client,
            service=self.service,
            service_code="walk30",
            service_name="30 Minute Walk",
            service_label="30 Minute Walk",
            start_dt=self.start_dt,
            end_dt=self.end_dt,
            location="Test Park 2",
            dogs=1,
            status="confirmed",
            price_cents=3000
        )
        
        invoice = {
            "id": "in_test123",
            "lines": {
                "data": [
                    {
                        "metadata": {
                            "booking_id": str(self.booking.id),
                            "dogs": "2",
                        }
                    },
                    {
                        "metadata": {
                            "booking_id": str(booking2.id),
                            "location": "Different Park",
                        }
                    }
                ]
            }
        }
        
        validate_invoice_against_bookings(invoice)
        
        self.booking.refresh_from_db()
        booking2.refresh_from_db()
        
        self.assertTrue(self.booking.requires_admin_review)
        self.assertIn("dogs", self.booking.review_diff)
        
        self.assertTrue(booking2.requires_admin_review)
        self.assertIn("location", booking2.review_diff)
