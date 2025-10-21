"""
Tests for custom error pages (403, 404, 500).
"""

import pytest
from django.test import Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User


@pytest.mark.django_db
@override_settings(DEBUG=False, ALLOWED_HOSTS=['*'])
def test_404_page_renders():
    """Test that custom 404 page renders with dog-walking theme"""
    from django.test import RequestFactory
    from django.shortcuts import render
    
    factory = RequestFactory()
    request = factory.get('/nonexistent-page/')
    
    # Directly render the 404 template
    response = render(request, '404.html', status=404)
    
    assert response.status_code == 404
    content = response.content.decode('utf-8')
    assert "404" in content
    assert "We couldn't find that page" in content or "couldn't find that page" in content
    # Check for dog-walking theme emoji
    assert "🐕" in content or "dog" in content.lower()


@pytest.mark.django_db
@override_settings(DEBUG=False, ALLOWED_HOSTS=['*'])
def test_403_page_renders():
    """Test that custom 403 page renders with dog-walking theme"""
    client = Client()
    
    # Create a staff-only view to test 403
    from django.http import HttpResponse
    from django.views.decorators.http import require_http_methods
    from django.contrib.admin.views.decorators import staff_member_required
    
    @staff_member_required
    @require_http_methods(["GET"])
    def staff_only_view(request):
        return HttpResponse("Staff only")
    
    # Temporarily add the view to urlpatterns
    from django.urls import path
    from django.conf import settings
    from importlib import reload
    import newfarm.urls
    
    # Create a non-staff user and try to access a staff-only resource
    user = User.objects.create_user(username="testuser", password="testpass")
    client.login(username="testuser", password="testpass")
    
    # Try accessing Django admin (requires staff permission)
    response = client.get(f'/{settings.DJANGO_ADMIN_URL}')
    
    # Should get 302 redirect to login, not 403, because Django admin redirects
    # Instead, let's test by directly rendering the 403 template
    from django.shortcuts import render
    from django.test import RequestFactory
    
    factory = RequestFactory()
    request = factory.get('/test/')
    request.user = user
    
    response = render(request, '403.html', status=403)
    
    assert response.status_code == 403
    content = response.content.decode('utf-8')
    assert "403" in content
    assert "Access denied" in content or "access denied" in content.lower()
    # Check for dog-walking theme
    assert "paws" in content.lower() or "🐾" in content


@pytest.mark.django_db 
@override_settings(DEBUG=False, ALLOWED_HOSTS=['*'])
def test_500_page_renders():
    """Test that custom 500 page renders with dog-walking theme"""
    from django.test import RequestFactory
    from django.shortcuts import render
    
    factory = RequestFactory()
    request = factory.get('/test/')
    
    # Directly render the 500 template
    response = render(request, '500.html', status=500)
    
    assert response.status_code == 500
    content = response.content.decode('utf-8')
    assert "500" in content
    assert "Something went wrong" in content or "went wrong" in content.lower()
    # Check for dog-walking theme emoji
    assert "🦴" in content or "dog" in content.lower()


@pytest.mark.django_db
@override_settings(DEBUG=False, ALLOWED_HOSTS=['*'])
def test_error_pages_have_home_links():
    """Test that all error pages have links to return home"""
    from django.test import RequestFactory
    from django.shortcuts import render
    
    factory = RequestFactory()
    request = factory.get('/test/')
    
    for template, status_code in [('403.html', 403), ('404.html', 404), ('500.html', 500)]:
        response = render(request, template, status=status_code)
        content = response.content.decode('utf-8')
        
        # Check for home link
        assert 'href="/"' in content or 'Return Home' in content
