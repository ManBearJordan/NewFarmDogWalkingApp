"""
Tests for the new env helper and additional settings added in PR 3.
"""
import pytest
import os
from django.conf import settings
from importlib import reload


def test_env_helper_bool_parses_truthy_values(monkeypatch):
    """Test that env.bool() correctly parses various truthy values."""
    monkeypatch.setenv("TEST_BOOL", "1")
    import newfarm.settings as settings_module
    reload(settings_module)
    env = settings_module.env
    assert env.bool("TEST_BOOL") is True
    
    monkeypatch.setenv("TEST_BOOL", "true")
    reload(settings_module)
    assert env.bool("TEST_BOOL") is True
    
    monkeypatch.setenv("TEST_BOOL", "yes")
    reload(settings_module)
    assert env.bool("TEST_BOOL") is True
    
    monkeypatch.setenv("TEST_BOOL", "on")
    reload(settings_module)
    assert env.bool("TEST_BOOL") is True


def test_env_helper_bool_parses_falsy_values(monkeypatch):
    """Test that env.bool() correctly parses various falsy values."""
    monkeypatch.setenv("TEST_BOOL", "0")
    import newfarm.settings as settings_module
    reload(settings_module)
    env = settings_module.env
    assert env.bool("TEST_BOOL") is False
    
    monkeypatch.setenv("TEST_BOOL", "false")
    reload(settings_module)
    assert env.bool("TEST_BOOL") is False


def test_env_helper_bool_uses_default_when_not_set(monkeypatch):
    """Test that env.bool() uses default when env var is not set."""
    monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
    import newfarm.settings as settings_module
    reload(settings_module)
    env = settings_module.env
    assert env.bool("NONEXISTENT_VAR", default=True) is True
    assert env.bool("NONEXISTENT_VAR", default=False) is False


def test_env_helper_list_parses_comma_separated(monkeypatch):
    """Test that env.list() correctly parses comma-separated values."""
    monkeypatch.setenv("TEST_LIST", "HTTP_X_FORWARDED_PROTO,https")
    import newfarm.settings as settings_module
    reload(settings_module)
    env = settings_module.env
    result = env.list("TEST_LIST")
    assert result == ["HTTP_X_FORWARDED_PROTO", "https"]


def test_env_helper_list_strips_whitespace(monkeypatch):
    """Test that env.list() strips whitespace from values."""
    monkeypatch.setenv("TEST_LIST", " value1 , value2 , value3 ")
    import newfarm.settings as settings_module
    reload(settings_module)
    env = settings_module.env
    result = env.list("TEST_LIST")
    assert result == ["value1", "value2", "value3"]


def test_env_helper_list_uses_default(monkeypatch):
    """Test that env.list() uses default when env var is not set."""
    monkeypatch.delenv("NONEXISTENT_LIST", raising=False)
    import newfarm.settings as settings_module
    reload(settings_module)
    env = settings_module.env
    result = env.list("NONEXISTENT_LIST", default=["default1", "default2"])
    assert result == ["default1", "default2"]


def test_env_helper_str_returns_value(monkeypatch):
    """Test that env.str() returns the string value."""
    monkeypatch.setenv("TEST_STR", "test_value")
    import newfarm.settings as settings_module
    reload(settings_module)
    env = settings_module.env
    assert env.str("TEST_STR") == "test_value"


def test_env_helper_str_uses_default(monkeypatch):
    """Test that env.str() uses default when env var is not set."""
    monkeypatch.delenv("NONEXISTENT_STR", raising=False)
    import newfarm.settings as settings_module
    reload(settings_module)
    env = settings_module.env
    assert env.str("NONEXISTENT_STR", default="default_value") == "default_value"


def test_cf_visitor_header_is_defined():
    """Test that CF_VISITOR_HEADER is defined in settings."""
    from newfarm.settings import CF_VISITOR_HEADER
    assert CF_VISITOR_HEADER == "HTTP_CF_VISITOR"


def test_admins_is_configured():
    """Test that ADMINS is configured with default."""
    assert hasattr(settings, 'ADMINS')
    assert isinstance(settings.ADMINS, list)
    assert len(settings.ADMINS) > 0


def test_server_email_is_configured():
    """Test that SERVER_EMAIL is configured."""
    assert hasattr(settings, 'SERVER_EMAIL')
    assert isinstance(settings.SERVER_EMAIL, str)
    assert len(settings.SERVER_EMAIL) > 0


def test_logging_is_configured():
    """Test that LOGGING is configured."""
    assert hasattr(settings, 'LOGGING')
    assert isinstance(settings.LOGGING, dict)
    assert settings.LOGGING['version'] == 1
    assert 'handlers' in settings.LOGGING
    assert 'console' in settings.LOGGING['handlers']
    assert 'loggers' in settings.LOGGING
    assert 'django.request' in settings.LOGGING['loggers']


def test_admin_email_can_be_overridden(monkeypatch):
    """Test that ADMIN_EMAIL can be overridden via environment variable."""
    monkeypatch.setenv("ADMIN_EMAIL", "custom@example.com")
    import newfarm.settings as settings_module
    reload(settings_module)
    assert ("Admin", "custom@example.com") in settings_module.ADMINS


def test_server_email_can_be_overridden(monkeypatch):
    """Test that SERVER_EMAIL can be overridden via environment variable."""
    monkeypatch.setenv("SERVER_EMAIL", "custom-server@example.com")
    import newfarm.settings as settings_module
    reload(settings_module)
    assert settings_module.SERVER_EMAIL == "custom-server@example.com"


def test_secure_proxy_ssl_header_is_tuple():
    """Test that SECURE_PROXY_SSL_HEADER is a tuple as required by Django."""
    from newfarm.settings import SECURE_PROXY_SSL_HEADER
    assert isinstance(SECURE_PROXY_SSL_HEADER, tuple)
    assert len(SECURE_PROXY_SSL_HEADER) == 2
    assert SECURE_PROXY_SSL_HEADER[0] == "HTTP_X_FORWARDED_PROTO"
    assert SECURE_PROXY_SSL_HEADER[1] == "https"


def test_secure_proxy_ssl_header_can_be_overridden(monkeypatch):
    """Test that SECURE_PROXY_SSL_HEADER can be overridden via environment variable."""
    monkeypatch.setenv("SECURE_PROXY_SSL_HEADER", "HTTP_X_CUSTOM_PROTO,https")
    import newfarm.settings as settings_module
    reload(settings_module)
    assert settings_module.SECURE_PROXY_SSL_HEADER == ("HTTP_X_CUSTOM_PROTO", "https")
