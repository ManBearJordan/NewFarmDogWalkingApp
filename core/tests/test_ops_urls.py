import pytest
from django.test import Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.mark.django_db
class TestOpsURLs:
    """Test the /ops/ namespace routing"""

    def setup_method(self):
        """Set up test data"""
        self.client = Client()
        
        # Create a staff user
        self.staff_user = User.objects.create_user(
            username="staff", password="password", is_staff=True, is_superuser=True
        )

    def test_ops_root_redirects_to_ops_bookings(self):
        """Test that /ops/ redirects to /ops/bookings/"""
        self.client.login(username="staff", password="password")
        response = self.client.get("/ops/")
        
        assert response.status_code == 302
        assert response.url == "/ops/bookings/"

    def test_ops_bookings_redirects_to_bookings(self):
        """Test that /ops/bookings/ redirects to /bookings/"""
        self.client.login(username="staff", password="password")
        response = self.client.get("/ops/bookings/")
        
        assert response.status_code == 302
        assert response.url == "/bookings/"

    def test_ops_calendar_redirects_to_calendar(self):
        """Test that /ops/calendar/ redirects to /calendar/"""
        self.client.login(username="staff", password="password")
        response = self.client.get("/ops/calendar/")
        
        assert response.status_code == 302
        assert response.url == "/calendar/"

    def test_ops_subscriptions_redirects_to_subscriptions(self):
        """Test that /ops/subscriptions/ redirects to /subscriptions/"""
        self.client.login(username="staff", password="password")
        response = self.client.get("/ops/subscriptions/")
        
        assert response.status_code == 302
        assert response.url == "/subscriptions/"

    def test_ops_clients_redirects_to_clients(self):
        """Test that /ops/clients/ redirects to /clients/"""
        self.client.login(username="staff", password="password")
        response = self.client.get("/ops/clients/")
        
        assert response.status_code == 302
        assert response.url == "/clients/"

    def test_ops_pets_redirects_to_pets(self):
        """Test that /ops/pets/ redirects to /pets/"""
        self.client.login(username="staff", password="password")
        response = self.client.get("/ops/pets/")
        
        assert response.status_code == 302
        assert response.url == "/pets/"

    def test_ops_tags_redirects_to_tags(self):
        """Test that /ops/tags/ redirects to /crm/tags/"""
        self.client.login(username="staff", password="password")
        response = self.client.get("/ops/tags/")
        
        assert response.status_code == 302
        assert response.url == "/tags/"

    def test_ops_tools_redirects_to_admin_tools(self):
        """Test that /ops/tools/ redirects to /admin-tools/"""
        self.client.login(username="staff", password="password")
        response = self.client.get("/ops/tools/")
        
        assert response.status_code == 302
        assert response.url == "/admin-tools/"

    def test_ops_urls_are_temporary_redirects(self):
        """Test that /ops/ URLs use temporary (302) redirects, not permanent (301)"""
        self.client.login(username="staff", password="password")
        
        # Test a few key endpoints
        response = self.client.get("/ops/")
        assert response.status_code == 302  # Temporary redirect
        
        response = self.client.get("/ops/bookings/")
        assert response.status_code == 302  # Temporary redirect
        
        response = self.client.get("/ops/calendar/")
        assert response.status_code == 302  # Temporary redirect
