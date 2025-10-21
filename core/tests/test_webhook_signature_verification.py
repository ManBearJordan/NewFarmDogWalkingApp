import pytest
import json
from unittest.mock import patch, MagicMock
from django.test import Client as TestClient
from django.urls import reverse
from django.utils import timezone
from core.models import Client, Booking, Service, StripeSubscriptionLink, StripeSubscriptionSchedule


@pytest.mark.django_db
class TestWebhookSignatureVerification:
    """Test signature verification for webhook events"""

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

    @patch('core.views_webhooks.settings.STRIPE_WEBHOOK_SECRET', None)
    def test_webhook_without_secret_accepts_valid_json(self):
        """Test that webhook accepts valid JSON when no secret is configured"""
        webhook_payload = {
            "type": "invoice.finalized",
            "data": {
                "object": {
                    "id": "in_test_no_secret",
                    "customer": "cus_test123",
                    "lines": {"data": []}
                }
            }
        }
        
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(webhook_payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        assert response.content.decode() == "ok"

    @patch('core.views_webhooks.settings.STRIPE_WEBHOOK_SECRET', None)
    def test_webhook_without_secret_rejects_invalid_json(self):
        """Test that webhook rejects invalid JSON when no secret is configured"""
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=b'not valid json',
            content_type='application/json'
        )
        
        assert response.status_code == 400
        assert "invalid payload" in response.content.decode()

    @patch('core.views_webhooks.stripe.Webhook.construct_event')
    @patch('core.views_webhooks.settings.STRIPE_WEBHOOK_SECRET', 'whsec_test_secret')
    def test_webhook_with_secret_verifies_signature(self, mock_construct):
        """Test that webhook verifies signature when secret is configured"""
        mock_event = {
            "type": "invoice.finalized",
            "data": {
                "object": {
                    "id": "in_test_verified",
                    "customer": "cus_test123",
                    "lines": {"data": []}
                }
            }
        }
        mock_construct.return_value = mock_event
        
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(mock_event),
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='t=123,v1=abc'
        )
        
        assert response.status_code == 200
        assert mock_construct.called

    @patch('core.views_webhooks.stripe.Webhook.construct_event')
    @patch('core.views_webhooks.settings.STRIPE_WEBHOOK_SECRET', 'whsec_test_secret')
    def test_webhook_with_secret_rejects_invalid_signature(self, mock_construct):
        """Test that webhook rejects invalid signature"""
        mock_construct.side_effect = Exception("Invalid signature")
        
        webhook_payload = {
            "type": "invoice.finalized",
            "data": {"object": {"id": "in_test_invalid"}}
        }
        
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(webhook_payload),
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='t=123,v1=invalid'
        )
        
        assert response.status_code == 403
        assert "invalid signature" in response.content.decode()


@pytest.mark.django_db
class TestWebhookInvoiceHandling:
    """Test invoice event handling"""

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
            end_dt=timezone.now() + timezone.timedelta(minutes=30),
            location="Test Location",
            status="confirmed"
        )
        self.test_client = TestClient()

    @patch('core.views_webhooks.settings.STRIPE_WEBHOOK_SECRET', None)
    @patch('core.views_webhooks.process_invoice')
    def test_invoice_finalized_calls_process_invoice(self, mock_process):
        """Test that invoice.finalized event calls process_invoice"""
        mock_process.return_value = {"line_items": 1, "linked": 1, "updated": 1}
        
        webhook_payload = {
            "type": "invoice.finalized",
            "data": {
                "object": {
                    "id": "in_test_finalized",
                    "customer": "cus_test123",
                    "lines": {"data": []}
                }
            }
        }
        
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(webhook_payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        assert mock_process.called

    @patch('core.views_webhooks.settings.STRIPE_WEBHOOK_SECRET', None)
    @patch('core.views_webhooks.process_invoice')
    def test_invoice_paid_calls_process_invoice(self, mock_process):
        """Test that invoice.paid event calls process_invoice"""
        mock_process.return_value = {"line_items": 1, "linked": 1, "updated": 1}
        
        webhook_payload = {
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "in_test_paid",
                    "customer": "cus_test123",
                    "lines": {"data": []}
                }
            }
        }
        
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(webhook_payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        assert mock_process.called

    @patch('core.views_webhooks.settings.STRIPE_WEBHOOK_SECRET', None)
    @patch('core.views_webhooks.process_invoice')
    def test_invoice_payment_failed_calls_process_invoice(self, mock_process):
        """Test that invoice.payment_failed event calls process_invoice"""
        mock_process.return_value = {"line_items": 1, "linked": 1, "updated": 0}
        
        webhook_payload = {
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "id": "in_test_failed",
                    "customer": "cus_test123",
                    "lines": {"data": []}
                }
            }
        }
        
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(webhook_payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        assert mock_process.called

    @patch('core.views_webhooks.settings.STRIPE_WEBHOOK_SECRET', None)
    @patch('core.views_webhooks.process_invoice')
    def test_invoice_processing_error_returns_200(self, mock_process):
        """Test that invoice processing errors still return 200"""
        mock_process.side_effect = Exception("Processing error")
        
        webhook_payload = {
            "type": "invoice.finalized",
            "data": {
                "object": {
                    "id": "in_test_error",
                    "customer": "cus_test123",
                    "lines": {"data": []}
                }
            }
        }
        
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(webhook_payload),
            content_type='application/json'
        )
        
        # Should still return 200 (never 5xx)
        assert response.status_code == 200


@pytest.mark.django_db
class TestWebhookSubscriptionHandling:
    """Test subscription event handling"""

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
        self.link = StripeSubscriptionLink.objects.create(
            stripe_subscription_id="sub_test123",
            client=self.client,
            service_code="walk30",
            status="active",
            active=True
        )
        self.schedule = StripeSubscriptionSchedule.objects.create(
            sub=self.link,
            weekdays_csv="mon,wed,fri",
            default_time="10:30",
            days="MON,WED,FRI",
            start_time="10:30",
            location="Home",
            repeats="weekly"
        )
        self.test_client = TestClient()

    @patch('core.views_webhooks.settings.STRIPE_WEBHOOK_SECRET', None)
    @patch('core.views_webhooks.materialize_for_schedule')
    def test_subscription_deleted_deactivates_link(self, mock_materialize):
        """Test that subscription.deleted deactivates the link"""
        mock_materialize.return_value = {"created": 0, "removed": 5}
        
        webhook_payload = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_test123",
                    "status": "canceled"
                }
            }
        }
        
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(webhook_payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        self.link.refresh_from_db()
        assert self.link.active is False
        assert mock_materialize.called

    @patch('core.views_webhooks.settings.STRIPE_WEBHOOK_SECRET', None)
    @patch('core.views_webhooks.materialize_for_schedule')
    def test_subscription_canceled_status_deactivates_link(self, mock_materialize):
        """Test that canceled status deactivates the link"""
        mock_materialize.return_value = {"created": 0, "removed": 3}
        
        webhook_payload = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test123",
                    "status": "canceled"
                }
            }
        }
        
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(webhook_payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        self.link.refresh_from_db()
        assert self.link.active is False

    @patch('core.views_webhooks.settings.STRIPE_WEBHOOK_SECRET', None)
    @patch('core.views_webhooks.materialize_for_schedule')
    def test_subscription_updated_rematerializes(self, mock_materialize):
        """Test that subscription.updated calls materialize_for_schedule"""
        mock_materialize.return_value = {"created": 2, "removed": 0}
        
        webhook_payload = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test123",
                    "status": "active"
                }
            }
        }
        
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(webhook_payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        assert mock_materialize.called

    @patch('core.views_webhooks.settings.STRIPE_WEBHOOK_SECRET', None)
    def test_subscription_event_without_link_returns_200(self):
        """Test that subscription event without local link returns 200"""
        webhook_payload = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_unknown",
                    "status": "active"
                }
            }
        }
        
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(webhook_payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200

    @patch('core.views_webhooks.settings.STRIPE_WEBHOOK_SECRET', None)
    @patch('core.views_webhooks.materialize_for_schedule')
    def test_subscription_event_error_returns_200(self, mock_materialize):
        """Test that subscription processing errors still return 200"""
        mock_materialize.side_effect = Exception("Materialization error")
        
        webhook_payload = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test123",
                    "status": "active"
                }
            }
        }
        
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(webhook_payload),
            content_type='application/json'
        )
        
        # Should still return 200 (never 5xx)
        assert response.status_code == 200


@pytest.mark.django_db
class TestWebhookUnhandledEvents:
    """Test handling of unhandled event types"""

    def setup_method(self):
        """Set up test client"""
        self.test_client = TestClient()

    @patch('core.views_webhooks.settings.STRIPE_WEBHOOK_SECRET', None)
    def test_unhandled_event_type_returns_200(self):
        """Test that unhandled event types return 200"""
        webhook_payload = {
            "type": "charge.succeeded",
            "data": {
                "object": {
                    "id": "ch_test123"
                }
            }
        }
        
        response = self.test_client.post(
            '/stripe/webhooks/',
            data=json.dumps(webhook_payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        assert response.content.decode() == "ok"
