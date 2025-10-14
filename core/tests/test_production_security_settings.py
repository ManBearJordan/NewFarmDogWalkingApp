import pytest
import os
from django.conf import settings
from importlib import reload


def test_production_flag_defaults_to_false(monkeypatch):
    """Test that PRODUCTION defaults to False when env var is not set."""
    # Clear the env var if it exists
    monkeypatch.delenv("PRODUCTION", raising=False)
    # Reload settings to pick up the change
    import newfarm.settings as settings_module
    reload(settings_module)
    assert settings_module.PRODUCTION is False


def test_production_flag_enabled_when_set_to_1(monkeypatch):
    """Test that PRODUCTION is True when env var is set to '1'."""
    monkeypatch.setenv("PRODUCTION", "1")
    import newfarm.settings as settings_module
    reload(settings_module)
    assert settings_module.PRODUCTION is True


def test_production_flag_disabled_when_set_to_0(monkeypatch):
    """Test that PRODUCTION is False when env var is set to '0'."""
    monkeypatch.setenv("PRODUCTION", "0")
    import newfarm.settings as settings_module
    reload(settings_module)
    assert settings_module.PRODUCTION is False


def test_security_settings_disabled_in_dev(monkeypatch):
    """Test that security settings are disabled when PRODUCTION=0."""
    monkeypatch.setenv("PRODUCTION", "0")
    import newfarm.settings as settings_module
    reload(settings_module)
    assert settings_module.SECURE_SSL_REDIRECT is False
    assert settings_module.SESSION_COOKIE_SECURE is False
    assert settings_module.CSRF_COOKIE_SECURE is False
    assert settings_module.SECURE_HSTS_SECONDS == 0
    assert settings_module.SECURE_HSTS_INCLUDE_SUBDOMAINS is False
    assert settings_module.SECURE_HSTS_PRELOAD is False
    assert settings_module.SECURE_PROXY_SSL_HEADER is None


def test_security_settings_enabled_in_production(monkeypatch):
    """Test that security settings are enabled when PRODUCTION=1."""
    monkeypatch.setenv("PRODUCTION", "1")
    import newfarm.settings as settings_module
    reload(settings_module)
    assert settings_module.SECURE_SSL_REDIRECT is True
    assert settings_module.SESSION_COOKIE_SECURE is True
    assert settings_module.CSRF_COOKIE_SECURE is True
    assert settings_module.SECURE_HSTS_SECONDS == 31536000  # 1 year in seconds
    assert settings_module.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert settings_module.SECURE_HSTS_PRELOAD is True
    assert settings_module.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")


def test_csrf_trusted_origins_empty_by_default(monkeypatch):
    """Test that CSRF_TRUSTED_ORIGINS includes production domain by default."""
    monkeypatch.delenv("CSRF_TRUSTED_ORIGINS", raising=False)
    import newfarm.settings as settings_module
    reload(settings_module)
    assert settings_module.CSRF_TRUSTED_ORIGINS == ["https://app.newfarmdogwalking.com.au"]


def test_csrf_trusted_origins_parses_comma_separated(monkeypatch):
    """Test that CSRF_TRUSTED_ORIGINS parses comma-separated values."""
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "https://example.com,https://app.example.com")
    import newfarm.settings as settings_module
    reload(settings_module)
    assert settings_module.CSRF_TRUSTED_ORIGINS == ["https://example.com", "https://app.example.com"]


def test_csrf_trusted_origins_strips_whitespace(monkeypatch):
    """Test that CSRF_TRUSTED_ORIGINS strips whitespace from values."""
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", " https://example.com , https://app.example.com ")
    import newfarm.settings as settings_module
    reload(settings_module)
    assert settings_module.CSRF_TRUSTED_ORIGINS == ["https://example.com", "https://app.example.com"]


def test_csrf_trusted_origins_ignores_empty_values(monkeypatch):
    """Test that CSRF_TRUSTED_ORIGINS ignores empty values."""
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "https://example.com,,https://app.example.com,")
    import newfarm.settings as settings_module
    reload(settings_module)
    assert settings_module.CSRF_TRUSTED_ORIGINS == ["https://example.com", "https://app.example.com"]
