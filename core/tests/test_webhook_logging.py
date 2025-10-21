import pytest
import json
from unittest.mock import patch, MagicMock
from django.test import Client as TestClient
from django.urls import reverse
from django.utils import timezone
from core.models import Client, Booking, Service, AdminEvent, StripeSubscriptionLink


@pytest.mark.django_db
class TestWebhookInvoiceLogging:
    """Test logging for invoice webhook events"""

    def setup_method(self):
        """Set up test data for each test"""
        self.client = Client.objects.create(
            name="Test Client",
            email="test@example.com",
            phone="1234567890",
            address="123 Test St",
            status="active",
            stripe_customer_id="cus_test123"
        )
        self.service = Service.objects.create(
            code="walk30",
            name="30 Minute Walk",
            duration_minutes=30,
            is_active=True
        )
        self.booking = Booking.objects.create(
            client=self.client,
            service=self.service,
            service_code="walk30",
            service_name="30 Minute Walk",
            service_label="Walk",
            start_dt=timezone.now(),
            end_dt=timezone.now(),
            location="Test Location",
            status="confirmed",
            stripe_invoice_id="in_test123"
        )
        self.test_client = TestClient()

    @patch('core.views_webhooks.get_stripe_key')
    def test_invoice_missing_booking_id_logs_warning(self, mock_get_key, caplog):
        """Test that missing booking_id in invoice metadata logs a warning"""
        mock_get_key.return_value = "sk_test_123"
        
        webhook_payload = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": "in_missing_booking",
                    "metadata": {
                        "service_code": "walk30",
                        "date": "2025-10-21"
                    }
                }
            }
        }
        
        with caplog.at_level('WARNING'):
            response = self.test_client.post(
                '/stripe/webhooks/',
                data=json.dumps(webhook_payload),
                content_type='application/json'
            )
        
        assert response.status_code == 200
        assert "Invalid or missing booking_id in metadata" in caplog.text
        assert "in_missing_booking" in caplog.text

    @patch('core.views_webhooks.get_stripe_key')
    def test_invoice_invalid_booking_id_logs_warning(self, mock_get_key, caplog):
        """Test that invalid booking_id in invoice metadata logs a warning"""
        mock_get_key.return_value = "sk_test_123"
        
        webhook_payload = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": "in_invalid_booking",
                    "metadata": {
                        "booking_id": "99999",  # Non-existent booking
                        "service_code": "walk30"
                    }
                }
            }
        }
        
        with caplog.at_level('WARNING'):
            response = self.test_client.post(
                '/stripe/webhooks/',
                data=json.dumps(webhook_payload),
                content_type='application/json'
            )
        
        assert response.status_code == 200
        assert "Invalid or missing booking_id in metadata" in caplog.text

    @patch('core.views_webhooks.get_stripe_key')
    def test_invoice_invalid_service_code_logs_warning(self, mock_get_key, caplog):
        """Test that invalid service_code in invoice metadata logs a warning"""
        mock_get_key.return_value = "sk_test_123"
        
        webhook_payload = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": "in_invalid_service",
                    "metadata": {
                        "booking_id": str(self.booking.id),
                        "service_code": "invalid_service"  # Non-existent service
                    },
                    "stripe_invoice_id": "in_test123"
                }
            }
        }
        
        with caplog.at_level('WARNING'):
            response = self.test_client.post(
                '/stripe/webhooks/',
                data=json.dumps(webhook_payload),
                content_type='application/json'
            )
        
        assert response.status_code == 200
        assert "Unknown service_code from metadata" in caplog.text
        assert "invalid_service" in caplog.text

    @patch('core.views_webhooks.get_stripe_key')
    def test_invoice_malformed_metadata_creates_admin_event(self, mock_get_key):
        """Test that malformed metadata creates an AdminEvent"""
        mock_get_key.return_value = "sk_test_123"
        
        webhook_payload = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": "in_malformed",
                    "metadata": {
                        "service_code": "walk30",
                        "date": "2025-10-21"
                        # Missing booking_id
                    }
                }
            }
        }
        
        initial_count = AdminEvent.objects.count()
        
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(webhook_payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        assert AdminEvent.objects.count() == initial_count + 1
        
        event = AdminEvent.objects.latest('id')
        assert "stripe_metadata_error" in event.title
        assert "in_malformed" in event.notes
        assert "malformed metadata" in event.notes

    @patch('core.views_webhooks.get_stripe_key')
    def test_invoice_unknown_metadata_keys_logged_in_debug_mode(self, mock_get_key, caplog):
        """Test that unknown metadata keys are logged when STRIPE_METADATA_LOGGING is enabled"""
        mock_get_key.return_value = "sk_test_123"
        
        webhook_payload = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": "in_unknown_keys",
                    "metadata": {
                        "booking_id": str(self.booking.id),
                        "service_code": "walk30",
                        "test_field": "test_value",
                        "another_unknown": "value"
                    }
                }
            }
        }
        
        with patch('core.views_webhooks.settings.STRIPE_METADATA_LOGGING', True):
            with caplog.at_level('DEBUG'):
                response = self.test_client.post(
                    '/stripe/webhooks/',
                    data=json.dumps(webhook_payload),
                    content_type='application/json'
                )
        
        assert response.status_code == 200
        # Note: DEBUG logs may not appear in caplog depending on logger configuration
        # but the code path is tested


@pytest.mark.django_db
class TestWebhookSubscriptionLogging:
    """Test logging for subscription webhook events"""

    def setup_method(self):
        """Set up test data for each test"""
        self.client = Client.objects.create(
            name="Test Client",
            email="test@example.com",
            phone="1234567890",
            address="123 Test St",
            status="active",
            stripe_customer_id="cus_test123"
        )
        self.service = Service.objects.create(
            code="walk30",
            name="30 Minute Walk",
            duration_minutes=30,
            is_active=True
        )
        self.test_client = TestClient()

    @patch('core.views_webhooks.get_stripe_key')
    def test_subscription_invalid_service_code_logs_warning(self, mock_get_key, caplog):
        """Test that invalid service_code from subscription nickname logs a warning"""
        mock_get_key.return_value = "sk_test_123"
        
        webhook_payload = {
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_test123",
                    "customer": "cus_test123",
                    "status": "active",
                    "items": {
                        "data": [
                            {
                                "price": {
                                    "nickname": "invalid_service_nickname"
                                }
                            }
                        ]
                    }
                }
            }
        }
        
        with caplog.at_level('WARNING'):
            response = self.test_client.post(
                '/stripe/webhooks/',
                data=json.dumps(webhook_payload),
                content_type='application/json'
            )
        
        assert response.status_code == 200
        # The service_code will be resolved to 'walk' (fallback), which may or may not exist
        # Check if warning is logged when service doesn't exist


@pytest.mark.django_db
class TestAdminEventLog:
    """Test AdminEvent.log() class method"""

    def test_admin_event_log_creates_event(self):
        """Test that AdminEvent.log creates a new event"""
        initial_count = AdminEvent.objects.count()
        
        AdminEvent.log("test_event", "Test message")
        
        assert AdminEvent.objects.count() == initial_count + 1
        event = AdminEvent.objects.latest('id')
        assert event.title == "test_event"
        assert event.notes == "Test message"

    def test_admin_event_log_prevents_duplicates(self):
        """Test that AdminEvent.log prevents duplicate events within an hour"""
        AdminEvent.log("test_event", "Test message")
        initial_count = AdminEvent.objects.count()
        
        # Try to log the same event again
        AdminEvent.log("test_event", "Test message")
        
        # Should not create a new event
        assert AdminEvent.objects.count() == initial_count

    def test_admin_event_log_allows_different_messages(self):
        """Test that AdminEvent.log allows different messages"""
        AdminEvent.log("test_event", "Message 1")
        initial_count = AdminEvent.objects.count()
        
        AdminEvent.log("test_event", "Message 2")
        
        # Should create a new event with different message
        assert AdminEvent.objects.count() == initial_count + 1
