"""
Integration tests for Cloudflare Tunnel SSL/proxy configuration.

This test suite validates that the application works reliably under Cloudflare 
Tunnel with proper SSL redirect and proxy header detection.
"""
import pytest
from importlib import reload


def test_cloudflare_production_defaults(monkeypatch):
    """
    Test that PRODUCTION=1 enables all required Cloudflare-friendly settings.
    
    This validates the implementation plan requirement:
    - SECURE_SSL_REDIRECT=1 (enabled)
    - SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https')
    - USE_X_FORWARDED_HOST=True
    """
    monkeypatch.setenv("PRODUCTION", "1")
    # Clear any explicit overrides
    monkeypatch.delenv("SECURE_SSL_REDIRECT", raising=False)
    monkeypatch.delenv("SECURE_PROXY_SSL_HEADER", raising=False)
    monkeypatch.delenv("USE_X_FORWARDED_HOST", raising=False)
    
    import newfarm.settings as settings_module
    reload(settings_module)
    
    # Verify PRODUCTION mode is enabled
    assert settings_module.PRODUCTION is True
    
    # Verify SSL redirect is enabled
    assert settings_module.SECURE_SSL_REDIRECT is True, \
        "SECURE_SSL_REDIRECT should be enabled in production"
    
    # Verify proxy SSL header is configured
    assert settings_module.SECURE_PROXY_SSL_HEADER == ('HTTP_X_FORWARDED_PROTO', 'https'), \
        "SECURE_PROXY_SSL_HEADER should be set to detect X-Forwarded-Proto"
    
    # Verify X-Forwarded-Host is trusted
    assert settings_module.USE_X_FORWARDED_HOST is True, \
        "USE_X_FORWARDED_HOST should be enabled in production"


def test_cloudflare_with_explicit_env_vars(monkeypatch):
    """
    Test that explicit .env settings work as documented.
    
    This validates the .env.example configuration:
    - SECURE_SSL_REDIRECT=1
    - SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https
    - USE_X_FORWARDED_HOST=1
    """
    monkeypatch.setenv("PRODUCTION", "1")
    monkeypatch.setenv("SECURE_SSL_REDIRECT", "1")
    monkeypatch.setenv("SECURE_PROXY_SSL_HEADER", "HTTP_X_FORWARDED_PROTO,https")
    monkeypatch.setenv("USE_X_FORWARDED_HOST", "1")
    
    import newfarm.settings as settings_module
    reload(settings_module)
    
    assert settings_module.SECURE_SSL_REDIRECT is True
    assert settings_module.SECURE_PROXY_SSL_HEADER == ('HTTP_X_FORWARDED_PROTO', 'https')
    assert settings_module.USE_X_FORWARDED_HOST is True


def test_can_disable_ssl_redirect_for_debugging(monkeypatch):
    """
    Test that SECURE_SSL_REDIRECT can be temporarily disabled if needed.
    
    While the default is enabled, operators should be able to disable it
    for debugging without having to edit code.
    """
    monkeypatch.setenv("PRODUCTION", "1")
    monkeypatch.setenv("SECURE_SSL_REDIRECT", "0")
    
    import newfarm.settings as settings_module
    reload(settings_module)
    
    assert settings_module.PRODUCTION is True
    assert settings_module.SECURE_SSL_REDIRECT is False, \
        "Should be able to disable SSL redirect via env var"
    # Other security settings should remain enabled
    assert settings_module.SECURE_PROXY_SSL_HEADER == ('HTTP_X_FORWARDED_PROTO', 'https')
    assert settings_module.USE_X_FORWARDED_HOST is True


def test_custom_proxy_header_format(monkeypatch):
    """
    Test that custom proxy header format is parsed correctly.
    
    The env var uses comma-separated format: "HEADER_NAME,value"
    """
    monkeypatch.setenv("PRODUCTION", "1")
    monkeypatch.setenv("SECURE_PROXY_SSL_HEADER", "HTTP_X_CUSTOM_PROTO,https")
    
    import newfarm.settings as settings_module
    reload(settings_module)
    
    assert settings_module.SECURE_PROXY_SSL_HEADER == ('HTTP_X_CUSTOM_PROTO', 'https')


def test_malformed_proxy_header_falls_back_to_default(monkeypatch):
    """
    Test that malformed SECURE_PROXY_SSL_HEADER falls back to standard format.
    """
    monkeypatch.setenv("PRODUCTION", "1")
    monkeypatch.setenv("SECURE_PROXY_SSL_HEADER", "malformed-value-no-comma")
    
    import newfarm.settings as settings_module
    reload(settings_module)
    
    # Should fall back to the standard header
    assert settings_module.SECURE_PROXY_SSL_HEADER == ('HTTP_X_FORWARDED_PROTO', 'https')


def test_development_mode_disables_ssl_by_default(monkeypatch):
    """
    Test that development mode (PRODUCTION=0) disables SSL redirect by default.
    
    This ensures local development doesn't require HTTPS.
    """
    monkeypatch.setenv("PRODUCTION", "0")
    monkeypatch.delenv("SECURE_SSL_REDIRECT", raising=False)
    
    import newfarm.settings as settings_module
    reload(settings_module)
    
    assert settings_module.PRODUCTION is False
    assert settings_module.SECURE_SSL_REDIRECT is False
    assert settings_module.USE_X_FORWARDED_HOST is False
    assert settings_module.SECURE_PROXY_SSL_HEADER is None


def test_cloudflare_middleware_is_installed(monkeypatch):
    """
    Test that the CF-Visitor fallback middleware is properly installed.
    
    This middleware provides extra safety when Cloudflare sends CF-Visitor
    instead of X-Forwarded-Proto.
    """
    monkeypatch.setenv("PRODUCTION", "1")
    
    import newfarm.settings as settings_module
    reload(settings_module)
    
    # Check that the middleware is in the list
    assert 'newfarm.settings.SECURE_PROXY_SSL_HEADER_FALLBACK' in settings_module.MIDDLEWARE, \
        "CF-Visitor fallback middleware should be installed"
    
    # It should be right after SecurityMiddleware (at index 1)
    security_idx = settings_module.MIDDLEWARE.index('django.middleware.security.SecurityMiddleware')
    fallback_idx = settings_module.MIDDLEWARE.index('newfarm.settings.SECURE_PROXY_SSL_HEADER_FALLBACK')
    assert fallback_idx == security_idx + 1, \
        "CF-Visitor fallback should be right after SecurityMiddleware"
