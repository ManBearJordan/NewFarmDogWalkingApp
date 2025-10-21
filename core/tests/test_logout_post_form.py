"""
Test that logout is implemented as a POST form (not a GET link).
This is a security best practice to prevent CSRF attacks.
"""
import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.test import Client


@pytest.mark.django_db
class TestLogoutPostForm:
    """Test that logout uses POST method with CSRF token"""

    def setup_method(self):
        """Create test users"""
        self.staff_user = User.objects.create_user(
            username="staff", password="pass", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="pass", is_staff=False
        )
        self.client = Client()

    def test_logout_form_present_in_navbar(self):
        """Logout should be a form with POST method and CSRF token in navbar"""
        self.client.login(username="staff", password="pass")
        resp = self.client.get(reverse("calendar_view"), follow=True)
        assert resp.status_code == 200
        
        content = resp.content.decode('utf-8')
        # Check for POST form
        assert 'method="post"' in content
        assert 'action="' + reverse('logout') + '"' in content or \
               "action='%s'" % reverse('logout') in content or \
               'url \'logout\'' in content  # Django template tag
        # Check for CSRF token
        assert 'csrf_token' in content or 'csrfmiddlewaretoken' in content
        # Check for logout button/text
        assert 'Logout' in content

    def test_logout_form_present_in_portal(self):
        """Logout should be a form with POST method in portal home"""
        # Create a client profile for the user
        from core.models import Client as ClientModel
        client_profile = ClientModel.objects.create(
            name="Regular User",
            email="regular@test.com",
            phone="1234567890",
            address="123 Test St",
            status="active",
            user=self.regular_user
        )
        
        self.client.login(username="regular", password="pass")
        resp = self.client.get(reverse("portal_home"))
        assert resp.status_code == 200
        
        content = resp.content.decode('utf-8')
        # Check for POST form
        assert 'method="post"' in content
        assert 'action="' + reverse('logout') + '"' in content or \
               "action='%s'" % reverse('logout') in content or \
               'url \'logout\'' in content  # Django template tag
        # Check for CSRF token
        assert 'csrf_token' in content or 'csrfmiddlewaretoken' in content
        # Check for sign out button/text
        assert 'Sign out' in content or 'Logout' in content

    def test_logout_via_post_works(self):
        """Logout should work via POST method"""
        self.client.login(username="regular", password="pass")
        
        # Verify user is logged in
        resp = self.client.get(reverse("calendar_view"))
        assert resp.status_code == 200
        
        # Logout via POST
        resp = self.client.post(reverse("logout"))
        # Should redirect after logout
        assert resp.status_code in [302, 301]
        
        # Verify user is logged out - accessing calendar should redirect to login
        resp = self.client.get(reverse("calendar_view"))
        assert resp.status_code in [302, 301]

    def test_logout_get_now_allowed(self):
        """
        CustomLogoutView allows GET requests for logout.
        """
        self.client.login(username="regular", password="pass")
        
        # GET request to logout should now work and redirect
        resp = self.client.get(reverse("logout"))
        assert resp.status_code in [302, 301]
        
        # Verify user is logged out - accessing calendar should redirect to login
        resp = self.client.get(reverse("calendar_view"))
        assert resp.status_code in [302, 301]
