import pytest
from django.test import RequestFactory
from django.contrib.auth.models import User
from core.models import AdminEvent, Booking, Client, Service
from core.audit import emit


@pytest.mark.django_db
class TestAuditEmit:
    """Test the audit.emit() function"""

    def setup_method(self):
        """Set up test data"""
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.client = Client.objects.create(
            name="Test Client",
            email="test@example.com",
            phone="1234567890",
            address="123 Test St",
            status="active"
        )
        self.service = Service.objects.create(
            code="walk30",
            name="30 Minute Walk",
            duration_minutes=30,
            is_active=True
        )

    def test_emit_creates_admin_event(self):
        """Test that emit creates an AdminEvent"""
        initial_count = AdminEvent.objects.count()
        
        ev = emit(
            "test.event",
            message="Test message",
            actor=self.user,
            context={"key": "value"}
        )
        
        assert AdminEvent.objects.count() == initial_count + 1
        assert ev is not None
        assert ev.event_type == "test.event"
        assert ev.message == "Test message"
        assert ev.actor == self.user
        assert ev.context == {"key": "value"}

    def test_emit_with_booking(self):
        """Test emit with a booking reference"""
        booking = Booking.objects.create(
            client=self.client,
            service=self.service,
            service_code="walk30",
            service_name="30 Minute Walk",
            service_label="Walk",
            start_dt="2025-10-22 10:00:00+10:00",
            end_dt="2025-10-22 10:30:00+10:00",
            location="Home",
            status="pending"
        )
        
        ev = emit(
            "booking.created.portal",
            message="Portal booking created",
            actor=self.user,
            booking=booking,
            context={"client_id": self.client.id}
        )
        
        assert ev is not None
        assert ev.booking == booking
        assert ev.event_type == "booking.created.portal"

    def test_emit_with_anonymous_user(self):
        """Test emit safely handles anonymous users"""
        from django.contrib.auth.models import AnonymousUser
        
        ev = emit(
            "webhook.invoice",
            message="Invoice processed",
            actor=AnonymousUser(),
            context={"invoice_id": "inv_123"}
        )
        
        assert ev is not None
        assert ev.actor is None
        assert ev.event_type == "webhook.invoice"

    def test_emit_with_none_actor(self):
        """Test emit safely handles None actor"""
        ev = emit(
            "webhook.subscription.updated",
            message="Subscription updated",
            actor=None,
            context={"subscription_id": "sub_123"}
        )
        
        assert ev is not None
        assert ev.actor is None

    def test_emit_failure_does_not_raise(self):
        """Test that emit failures don't raise exceptions"""
        # Try to create an event with invalid data (extremely long event_type)
        ev = emit(
            "x" * 200,  # Exceeds max_length of 100
            message="Should fail gracefully"
        )
        
        # emit should return None on failure but not raise
        # This behavior depends on implementation
        # The key is it doesn't crash the calling code
