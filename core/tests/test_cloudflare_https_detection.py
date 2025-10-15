"""
Tests for Cloudflare HTTPS detection via CF-Visitor header.
"""
import pytest
from django.test import RequestFactory
from django.http import HttpResponse
from newfarm.settings import SECURE_PROXY_SSL_HEADER_FALLBACK


@pytest.fixture
def middleware():
    """Create middleware instance."""
    def get_response(request):
        return HttpResponse("OK")
    return SECURE_PROXY_SSL_HEADER_FALLBACK(get_response)


@pytest.fixture
def request_factory():
    """Create request factory."""
    return RequestFactory()


def test_cf_visitor_header_with_https_sets_secure(middleware, request_factory):
    """Test that CF-Visitor header with https scheme marks request as secure."""
    request = request_factory.get('/')
    # Cloudflare sends CF-Visitor header with JSON like {"scheme":"https"}
    request.META['HTTP_CF_VISITOR'] = '{"scheme":"https"}'
    
    response = middleware(request)
    
    assert response.status_code == 200
    assert request.META['wsgi.url_scheme'] == 'https'
    assert request.is_secure() is True


def test_cf_visitor_header_with_http_does_not_set_secure(middleware, request_factory):
    """Test that CF-Visitor header with http scheme does not mark request as secure."""
    request = request_factory.get('/')
    request.META['HTTP_CF_VISITOR'] = '{"scheme":"http"}'
    
    response = middleware(request)
    
    assert response.status_code == 200
    # Should not modify the request if not https
    assert 'wsgi.url_scheme' not in request.META or request.META['wsgi.url_scheme'] != 'https'


def test_no_cf_visitor_header_does_not_modify_request(middleware, request_factory):
    """Test that requests without CF-Visitor header are not modified."""
    request = request_factory.get('/')
    
    response = middleware(request)
    
    assert response.status_code == 200
    # Should not modify the request
    assert 'wsgi.url_scheme' not in request.META or request.META['wsgi.url_scheme'] != 'https'


def test_cf_visitor_header_with_malformed_json(middleware, request_factory):
    """Test that malformed CF-Visitor header doesn't break the middleware."""
    request = request_factory.get('/')
    request.META['HTTP_CF_VISITOR'] = 'not valid json'
    
    # Should not raise an exception
    response = middleware(request)
    
    assert response.status_code == 200


def test_cf_visitor_header_partial_match(middleware, request_factory):
    """Test that partial https string in CF-Visitor marks as secure."""
    request = request_factory.get('/')
    # The middleware simply checks if 'https' is in the header value
    request.META['HTTP_CF_VISITOR'] = 'contains https somewhere'
    
    response = middleware(request)
    
    assert response.status_code == 200
    assert request.META['wsgi.url_scheme'] == 'https'
    assert request.is_secure() is True
