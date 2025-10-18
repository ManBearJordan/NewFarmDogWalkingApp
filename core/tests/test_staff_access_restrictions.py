"""
Test that admin-only views are properly restricted to staff users.
Non-staff authenticated users should not be able to access admin functionality.
"""
import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.test import Client
from core.models import Client as ClientModel, Pet, Tag, AdminEvent


@pytest.mark.django_db
class TestStaffAccessRestrictions:
    """Test that admin views require staff status"""

    def setup_method(self):
        """Create test users"""
        self.staff_user = User.objects.create_user(
            username="staff", password="pass", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="pass", is_staff=False
        )
        self.client = Client()

    def test_client_list_requires_staff(self):
        """Non-staff users should not access client list"""
        # Regular user should be denied
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("client_list"))
        assert resp.status_code in [301, 302, 403]  # Redirect or forbidden
        
        # Staff user should have access
        self.client.login(username="staff", password="pass")
        resp = self.client.get(reverse("client_list"), follow=True)
        assert resp.status_code == 200

    def test_client_create_requires_staff(self):
        """Non-staff users should not access client creation"""
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("client_create"))
        assert resp.status_code in [301, 302, 403]
        
        self.client.login(username="staff", password="pass")
        resp = self.client.get(reverse("client_create"), follow=True)
        assert resp.status_code == 200

    def test_pet_list_requires_staff(self):
        """Non-staff users should not access pet list"""
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("pet_list"))
        assert resp.status_code in [301, 302, 403]
        
        self.client.login(username="staff", password="pass")
        resp = self.client.get(reverse("pet_list"), follow=True)
        assert resp.status_code == 200

    def test_pet_create_requires_staff(self):
        """Non-staff users should not access pet creation"""
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("pet_create"))
        assert resp.status_code in [301, 302, 403]
        
        self.client.login(username="staff", password="pass")
        resp = self.client.get(reverse("pet_create"), follow=True)
        assert resp.status_code == 200

    def test_subscriptions_list_requires_staff(self):
        """Non-staff users should not access subscriptions"""
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("subscriptions_list"))
        assert resp.status_code in [301, 302, 403]
        
        self.client.login(username="staff", password="pass")
        resp = self.client.get(reverse("subscriptions_list"), follow=True)
        assert resp.status_code == 200

    def test_admin_tasks_list_requires_staff(self):
        """Non-staff users should not access admin tasks"""
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("admin_tasks_list"))
        assert resp.status_code in [301, 302, 403]
        
        self.client.login(username="staff", password="pass")
        resp = self.client.get(reverse("admin_tasks_list"), follow=True)
        assert resp.status_code == 200

    def test_admin_task_create_requires_staff(self):
        """Non-staff users should not create admin tasks"""
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("admin_task_create"))
        assert resp.status_code in [301, 302, 403]
        
        self.client.login(username="staff", password="pass")
        resp = self.client.get(reverse("admin_task_create"), follow=True)
        assert resp.status_code == 200

    def test_tags_list_requires_staff(self):
        """Non-staff users should not access tags"""
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("tags_list"))
        assert resp.status_code in [301, 302, 403]
        
        self.client.login(username="staff", password="pass")
        resp = self.client.get(reverse("tags_list"), follow=True)
        assert resp.status_code == 200

    def test_tag_create_requires_staff(self):
        """Non-staff users should not create tags"""
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("tag_create"))
        assert resp.status_code in [301, 302, 403]
        
        self.client.login(username="staff", password="pass")
        resp = self.client.get(reverse("tag_create"), follow=True)
        assert resp.status_code == 200

    def test_stripe_status_requires_staff(self):
        """Non-staff users should not access stripe status"""
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("stripe_status"))
        assert resp.status_code in [301, 302, 403]
        
        self.client.login(username="staff", password="pass")
        resp = self.client.get(reverse("stripe_status"), follow=True)
        assert resp.status_code == 200

    def test_reports_invoices_requires_staff(self):
        """Non-staff users should not access reports"""
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("reports_invoices_list"))
        assert resp.status_code in [301, 302, 403]
        
        self.client.login(username="staff", password="pass")
        resp = self.client.get(reverse("reports_invoices_list"), follow=True)
        assert resp.status_code == 200

    def test_booking_create_batch_requires_staff(self):
        """Non-staff users should not access batch booking creation"""
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("booking_create_batch"))
        assert resp.status_code in [301, 302, 403]
        
        self.client.login(username="staff", password="pass")
        resp = self.client.get(reverse("booking_create_batch"), follow=True)
        assert resp.status_code == 200

    def test_anonymous_users_redirected_to_login(self):
        """Anonymous users should be redirected to login"""
        resp = self.client.get(reverse("client_list"))
        assert resp.status_code in [301, 302]
        # Follow redirects to ensure we end up at login
        resp = self.client.get(reverse("client_list"), follow=True)
        assert '/login' in resp.redirect_chain[-1][0] or 'accounts/login' in resp.redirect_chain[-1][0]

    def test_booking_list_requires_staff(self):
        """Non-staff users should not access booking list"""
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("booking_list"))
        assert resp.status_code in [301, 302, 403]
        
        self.client.login(username="staff", password="pass")
        resp = self.client.get(reverse("booking_list"), follow=True)
        assert resp.status_code == 200

    def test_calendar_view_allows_all_authenticated_users(self):
        """Calendar view should be accessible to all authenticated users (staff and non-staff)"""
        # Non-staff authenticated user should have access
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("calendar_view"), follow=True)
        assert resp.status_code == 200
        
        # Staff user should also have access
        self.client.login(username="staff", password="pass")
        resp = self.client.get(reverse("calendar_view"), follow=True)
        assert resp.status_code == 200
