"""
Tests for access control decorators.
"""
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from core.access import require_superuser, require_client
from core.models import Client

User = get_user_model()


class RequireSuperuserTests(TestCase):
    """Test the require_superuser decorator."""

    def setUp(self):
        self.factory = RequestFactory()
        
        # Create a simple view wrapped with require_superuser
        @require_superuser
        def test_view(request):
            from django.http import HttpResponse
            return HttpResponse("success")
        
        self.test_view = test_view

    def test_unauthenticated_user_redirects_to_login(self):
        """Unauthenticated users should be redirected to login."""
        from django.contrib.auth.models import AnonymousUser
        request = self.factory.get('/ops/calendar/')
        request.user = AnonymousUser()
        
        response = self.test_view(request)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_non_superuser_gets_403(self):
        """Non-superuser authenticated users should get 403 (not redirect)."""
        user = User.objects.create_user(username='regular', password='pass')
        request = self.factory.get('/ops/calendar/')
        request.user = user
        
        response = self.test_view(request)
        
        # Important: should return 403, NOT redirect (to prevent loops)
        self.assertEqual(response.status_code, 403)

    def test_superuser_accesses_view(self):
        """Superusers should be able to access the view."""
        user = User.objects.create_superuser(username='admin', password='pass')
        request = self.factory.get('/ops/calendar/')
        request.user = user
        
        response = self.test_view(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"success")


class RequireClientTests(TestCase):
    """Test the require_client decorator."""

    def setUp(self):
        self.factory = RequestFactory()
        
        # Create a simple view wrapped with require_client
        @require_client
        def test_view(request):
            from django.http import HttpResponse
            return HttpResponse("success")
        
        self.test_view = test_view

    def test_unauthenticated_user_redirects_to_login(self):
        """Unauthenticated users should be redirected to login."""
        from django.contrib.auth.models import AnonymousUser
        request = self.factory.get('/portal/calendar/')
        request.user = AnonymousUser()
        
        response = self.test_view(request)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_user_without_client_gets_403(self):
        """Users without linked client profile should get 403."""
        user = User.objects.create_user(username='noclien', password='pass')
        request = self.factory.get('/portal/calendar/')
        request.user = user
        
        response = self.test_view(request)
        
        # Important: should return 403, NOT redirect (to prevent loops)
        self.assertEqual(response.status_code, 403)

    def test_user_with_client_accesses_view(self):
        """Users with linked client profile should access the view."""
        user = User.objects.create_user(username='client', password='pass')
        client = Client.objects.create(
            name='Test Client',
            email='test@example.com',
            phone='123456',
            address='Test Address',
            status='active',
            user=user
        )
        request = self.factory.get('/portal/calendar/')
        request.user = user
        
        response = self.test_view(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"success")
        # Check that client was stored in request
        self.assertEqual(request._nfdw_client, client)
