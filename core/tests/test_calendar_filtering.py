"""
Test calendar view filtering logic for admin and non-admin users.
"""
import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.utils import timezone
from datetime import timedelta
from core.models import Client as ClientModel, Booking


@pytest.mark.django_db
class TestCalendarFiltering:
    """Test that calendar view properly filters bookings based on user permissions"""

    def setup_method(self):
        """Create test users and clients"""
        # Create admin user (superuser)
        self.admin_user = User.objects.create_user(
            username="admin", password="pass", is_staff=True, is_superuser=True
        )
        
        # Create non-admin staff user with linked client
        self.staff_user = User.objects.create_user(
            username="staff", password="pass", is_staff=True, is_superuser=False
        )
        
        # Create regular staff user without linked client
        self.staff_no_client = User.objects.create_user(
            username="staff_no_client", password="pass", is_staff=True, is_superuser=False
        )
        
        # Create clients
        self.client1 = ClientModel.objects.create(
            name="Client One",
            email="client1@test.com",
            phone="1234567890",
            address="Address 1",
            status="active",
            user=self.staff_user  # Link to staff_user
        )
        
        self.client2 = ClientModel.objects.create(
            name="Client Two",
            email="client2@test.com",
            phone="0987654321",
            address="Address 2",
            status="active"
        )
        
        # Create bookings for both clients
        now = timezone.now()
        self.booking1 = Booking.objects.create(
            client=self.client1,
            service_code="walk",
            service_name="Dog Walk",
            service_label="Walk",
            start_dt=now,
            end_dt=now + timedelta(hours=1),
            location="Park",
            status="confirmed",
            price_cents=5000
        )
        
        self.booking2 = Booking.objects.create(
            client=self.client2,
            service_code="walk",
            service_name="Dog Walk",
            service_label="Walk",
            start_dt=now + timedelta(hours=2),
            end_dt=now + timedelta(hours=3),
            location="Beach",
            status="confirmed",
            price_cents=5000
        )
        
        self.test_client = TestClient()

    def test_admin_sees_all_bookings(self):
        """Admin users should see all bookings"""
        self.test_client.login(username="admin", password="pass")
        resp = self.test_client.get(reverse("calendar_view"), follow=True)
        assert resp.status_code == 200  # After following redirects
        
        # Check that calendar_days has data (both bookings should be counted)
        calendar_days = resp.context['calendar_days']
        # The bookings are in the current month, so they should appear
        total_bookings = sum(day['bookings'] for day in calendar_days.values())
        assert total_bookings == 2

    def test_non_admin_staff_with_client_sees_only_their_bookings(self):
        """Non-admin staff with linked client should see only their bookings"""
        self.test_client.login(username="staff", password="pass")
        resp = self.test_client.get(reverse("calendar_view"), follow=True)
        assert resp.status_code == 200  # After following redirects
        
        # Check that calendar_days only has bookings for client1
        calendar_days = resp.context['calendar_days']
        total_bookings = sum(day['bookings'] for day in calendar_days.values())
        assert total_bookings == 1

    def test_non_admin_staff_without_client_sees_all_bookings(self):
        """Non-admin staff without linked client should see all bookings"""
        self.test_client.login(username="staff_no_client", password="pass")
        resp = self.test_client.get(reverse("calendar_view"), follow=True)
        assert resp.status_code == 200  # After following redirects
        
        # Check that calendar_days has all bookings
        calendar_days = resp.context['calendar_days']
        total_bookings = sum(day['bookings'] for day in calendar_days.values())
        assert total_bookings == 2

    def test_day_detail_respects_client_filter(self):
        """Day detail view should respect client filtering"""
        # Get the date for booking1
        date_str = self.booking1.start_dt.date().isoformat()
        
        # Admin sees both bookings on that date (if they're on the same date)
        self.test_client.login(username="admin", password="pass")
        resp = self.test_client.get(reverse("calendar_view"), {'date': date_str}, follow=True)
        assert resp.status_code == 200  # After following redirects
        day_detail = resp.context.get('day_detail')
        if day_detail:
            # booking1 is on this date
            assert day_detail['bookings'].count() >= 1
        
        # Non-admin staff with client1 sees only booking1
        self.test_client.login(username="staff", password="pass")
        resp = self.test_client.get(reverse("calendar_view"), {'date': date_str}, follow=True)
        assert resp.status_code == 200  # After following redirects
        day_detail = resp.context.get('day_detail')
        if day_detail:
            bookings = list(day_detail['bookings'])
            assert len(bookings) == 1
            assert bookings[0].client == self.client1

    def test_deleted_bookings_not_shown(self):
        """Deleted bookings should not appear in calendar"""
        # Mark booking1 as deleted
        self.booking1.deleted = True
        self.booking1.save()
        
        # Admin should now see only 1 booking
        self.test_client.login(username="admin", password="pass")
        resp = self.test_client.get(reverse("calendar_view"), follow=True)
        assert resp.status_code == 200  # After following redirects
        
        calendar_days = resp.context['calendar_days']
        total_bookings = sum(day['bookings'] for day in calendar_days.values())
        assert total_bookings == 1

    def test_cancelled_bookings_not_shown(self):
        """Cancelled bookings should not appear in calendar"""
        # Mark booking1 as cancelled
        self.booking1.status = "cancelled"
        self.booking1.save()
        
        # Admin should now see only 1 booking
        self.test_client.login(username="admin", password="pass")
        resp = self.test_client.get(reverse("calendar_view"), follow=True)
        assert resp.status_code == 200  # After following redirects
        
        calendar_days = resp.context['calendar_days']
        total_bookings = sum(day['bookings'] for day in calendar_days.values())
        assert total_bookings == 1
