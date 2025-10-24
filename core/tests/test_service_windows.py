"""
Tests for Service Windows functionality.
"""
from django.test import TestCase
from django.utils import timezone
from datetime import time, datetime, timedelta
from zoneinfo import ZoneInfo

from core.models import Service
from core.models_service_windows import ServiceWindow


BRISBANE = ZoneInfo("Australia/Brisbane")


class ServiceWindowModelTestCase(TestCase):
    """Test the ServiceWindow model helpers."""

    def setUp(self):
        # Create test services
        self.group_walk = Service.objects.create(
            code="groupwalk",
            name="Group Walk",
            duration_minutes=60,
            is_active=True
        )
        self.private_walk = Service.objects.create(
            code="privatewalk",
            name="Private Walk",
            duration_minutes=30,
            is_active=True
        )
        
        # Create a service window for group walks only (08:30-10:30 daily)
        self.window = ServiceWindow.objects.create(
            title="Group Walk AM",
            active=True,
            weekday=-1,  # All days
            start_time=time(8, 30),
            end_time=time(10, 30),
            block_in_portal=True,
            warn_in_admin=True,
        )
        self.window.allowed_services.add(self.group_walk)

    def test_applies_on_all_days(self):
        """Test that window with weekday=-1 applies on any day."""
        # Monday
        dt = datetime(2025, 1, 6, 9, 0, tzinfo=BRISBANE)
        self.assertTrue(self.window.applies_on(dt))
        
        # Sunday
        dt = datetime(2025, 1, 12, 9, 0, tzinfo=BRISBANE)
        self.assertTrue(self.window.applies_on(dt))

    def test_applies_on_specific_weekday(self):
        """Test window that applies only on Monday (0)."""
        window = ServiceWindow.objects.create(
            title="Monday Special",
            active=True,
            weekday=0,  # Monday only
            start_time=time(9, 0),
            end_time=time(10, 0),
        )
        
        # Monday - should apply
        monday = datetime(2025, 1, 6, 9, 30, tzinfo=BRISBANE)
        self.assertTrue(window.applies_on(monday))
        
        # Tuesday - should not apply
        tuesday = datetime(2025, 1, 7, 9, 30, tzinfo=BRISBANE)
        self.assertFalse(window.applies_on(tuesday))

    def test_overlaps_time_range(self):
        """Test time overlap detection."""
        # Start: 09:00, End: 09:30 → overlaps with 08:30-10:30
        start = datetime(2025, 1, 6, 9, 0, tzinfo=BRISBANE)
        end = datetime(2025, 1, 6, 9, 30, tzinfo=BRISBANE)
        self.assertTrue(self.window.overlaps(start, end))
        
        # Start: 07:00, End: 08:00 → no overlap
        start = datetime(2025, 1, 6, 7, 0, tzinfo=BRISBANE)
        end = datetime(2025, 1, 6, 8, 0, tzinfo=BRISBANE)
        self.assertFalse(self.window.overlaps(start, end))
        
        # Start: 11:00, End: 12:00 → no overlap
        start = datetime(2025, 1, 6, 11, 0, tzinfo=BRISBANE)
        end = datetime(2025, 1, 6, 12, 0, tzinfo=BRISBANE)
        self.assertFalse(self.window.overlaps(start, end))

    def test_blocks_service_in_portal(self):
        """Test service blocking logic for portal bookings."""
        # Group walk is allowed, should not be blocked
        self.assertFalse(self.window.blocks_service_in_portal(self.group_walk))
        
        # Private walk is not in allowed list, should be blocked
        self.assertTrue(self.window.blocks_service_in_portal(self.private_walk))

    def test_blocks_service_when_no_allowed_list(self):
        """Test that window with empty allowed_services does not block anything."""
        window = ServiceWindow.objects.create(
            title="Open Window",
            active=True,
            weekday=-1,
            start_time=time(14, 0),
            end_time=time(16, 0),
            block_in_portal=True,
        )
        # No allowed services configured
        self.assertFalse(window.blocks_service_in_portal(self.private_walk))
        self.assertFalse(window.blocks_service_in_portal(self.group_walk))

    def test_inactive_window_does_not_apply(self):
        """Test that inactive windows are ignored."""
        self.window.active = False
        self.window.save()
        
        dt = datetime(2025, 1, 6, 9, 0, tzinfo=BRISBANE)
        self.assertFalse(self.window.applies_on(dt))

    def test_window_string_representation(self):
        """Test __str__ method."""
        expected = "Group Walk AM [All 08:30:00-10:30:00]"
        self.assertEqual(str(self.window), expected)
        
        # Test with specific weekday
        window = ServiceWindow.objects.create(
            title="Monday Special",
            weekday=0,
            start_time=time(9, 0),
            end_time=time(10, 0),
        )
        expected = "Monday Special [Mon 09:00:00-10:00:00]"
        self.assertEqual(str(window), expected)


class ServiceWindowPortalValidationTestCase(TestCase):
    """Test portal booking form validation with service windows."""

    def setUp(self):
        from core.models import Client
        from core.forms import PortalBookingForm
        
        # Create test client
        self.client = Client.objects.create(
            name="Test Client",
            email="test@example.com",
            phone="1234567890",
            address="123 Test St",
            status="active"
        )
        
        # Create test services
        self.group_walk = Service.objects.create(
            code="groupwalk",
            name="Group Walk",
            duration_minutes=60,
            is_active=True
        )
        self.private_walk = Service.objects.create(
            code="privatewalk",
            name="Private Walk",
            duration_minutes=30,
            is_active=True
        )
        
        # Create service window that only allows group walks (08:30-10:30)
        self.window = ServiceWindow.objects.create(
            title="Group Walk AM",
            active=True,
            weekday=-1,
            start_time=time(8, 30),
            end_time=time(10, 30),
            block_in_portal=True,
        )
        self.window.allowed_services.add(self.group_walk)

    def test_booking_allowed_service_during_window(self):
        """Test that booking an allowed service during window is permitted."""
        from core.forms import PortalBookingForm
        
        form_data = {
            'service': self.group_walk.id,
            'date': '2025-01-06',  # Monday
            'time': '09:00',  # Within 08:30-10:30 window
            'location': 'Home',
        }
        form = PortalBookingForm(data=form_data, client=self.client)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

    def test_booking_blocked_service_during_window(self):
        """Test that booking a blocked service during window is rejected."""
        from core.forms import PortalBookingForm
        
        form_data = {
            'service': self.private_walk.id,
            'date': '2025-01-06',  # Monday
            'time': '09:00',  # Within 08:30-10:30 window
            'location': 'Home',
        }
        form = PortalBookingForm(data=form_data, client=self.client)
        self.assertFalse(form.is_valid())
        self.assertIn('not bookable during', str(form.errors))

    def test_booking_blocked_service_outside_window(self):
        """Test that booking a blocked service outside window is permitted."""
        from core.forms import PortalBookingForm
        
        form_data = {
            'service': self.private_walk.id,
            'date': '2025-01-06',  # Monday
            'time': '14:00',  # Outside 08:30-10:30 window
            'location': 'Home',
        }
        form = PortalBookingForm(data=form_data, client=self.client)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
