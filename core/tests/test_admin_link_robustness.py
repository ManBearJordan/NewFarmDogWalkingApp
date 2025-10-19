"""
Test that admin link in base.html uses Django's URL tag for robustness.

This ensures the admin link works regardless of custom DJANGO_ADMIN_URL configuration.
"""
import pytest
from django.test import Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings


@pytest.mark.django_db
class TestAdminLinkRobustness:
    """Test that the admin link in base.html is robust and uses Django's url tag."""

    def setup_method(self):
        """Create a staff user for testing."""
        self.staff_user = User.objects.create_user(
            username="staffuser",
            password="testpass123",
            is_staff=True
        )
        self.client = Client()

    def test_admin_link_uses_url_tag(self):
        """
        Test that the admin link in the navbar uses {% url 'admin:index' %}.
        
        This ensures the link is robust and works with any DJANGO_ADMIN_URL configuration.
        """
        self.client.login(username="staffuser", password="testpass123")
        resp = self.client.get(reverse("calendar_view"), follow=True)
        assert resp.status_code == 200
        
        # The response should contain a link to Django Admin
        assert b'Django Admin' in resp.content
        
        # Get the expected admin URL from Django's URL resolver
        expected_admin_url = reverse('admin:index')
        
        # The admin link should use the proper URL from Django's URL resolver
        # not a hardcoded path like /{{ DJANGO_ADMIN_URL|default:'admin/' }}
        assert expected_admin_url.encode() in resp.content

    def test_admin_link_not_hardcoded(self):
        """
        Test that the admin link does not use a hardcoded pattern.
        
        The old pattern was: /{{ DJANGO_ADMIN_URL|default:'admin/' }}
        This should not appear in the rendered template.
        """
        self.client.login(username="staffuser", password="testpass123")
        resp = self.client.get(reverse("calendar_view"), follow=True)
        assert resp.status_code == 200
        
        # Should NOT contain the old hardcoded pattern remnants
        assert b'DJANGO_ADMIN_URL' not in resp.content
        
    def test_admin_link_resolves_correctly_with_custom_url(self):
        """
        Test that the admin link resolves correctly when DJANGO_ADMIN_URL is customized.
        
        This validates that using {% url 'admin:index' %} works with custom admin paths.
        """
        # Get the configured admin URL
        admin_url = getattr(settings, 'DJANGO_ADMIN_URL', 'admin/')
        
        # The Django URL resolver should return the correct path
        expected_path = f'/{admin_url}'
        actual_path = reverse('admin:index')
        
        assert actual_path == expected_path, \
            f"Admin URL should resolve to {expected_path}, got {actual_path}"
        
    def test_admin_link_visible_only_to_staff(self):
        """
        Test that the Django Admin link is only visible to staff users.
        """
        # Create a non-staff user
        regular_user = User.objects.create_user(
            username="regular",
            password="testpass123",
            is_staff=False
        )
        
        # Regular user should not see the admin dropdown
        self.client.login(username="regular", password="testpass123")
        resp = self.client.get(reverse("calendar_view"), follow=True)
        assert resp.status_code == 200
        
        # Should not contain Django Admin link
        admin_url = reverse('admin:index')
        # The link might be in the HTML but not visible due to staff check
        # We check that the Admin dropdown is not rendered for non-staff
        assert b'adminMenu' not in resp.content or b'Django Admin' not in resp.content
        
        # Staff user should see the admin link
        self.client.login(username="staffuser", password="testpass123")
        resp = self.client.get(reverse("calendar_view"), follow=True)
        assert resp.status_code == 200
        
        # Should contain both the admin menu and Django Admin link
        assert b'adminMenu' in resp.content
        assert b'Django Admin' in resp.content
        assert admin_url.encode() in resp.content
