import os
import pytest
from unittest.mock import patch
from django.test import TestCase
from core import secrets_config


class SecretsConfigTest(TestCase):
    """Tests for the secrets_config module."""
    
    def test_get_stripe_key_from_stripe_secret_key_env(self):
        """Test getting key from STRIPE_SECRET_KEY environment variable."""
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_123", "PRODUCTION": "0"}, clear=True):
            key = secrets_config.get_stripe_key()
            self.assertEqual(key, "sk_test_123")
    
    def test_get_stripe_key_from_stripe_api_key_env(self):
        """Test getting key from STRIPE_API_KEY environment variable as fallback."""
        with patch.dict(os.environ, {"STRIPE_API_KEY": "sk_test_456", "PRODUCTION": "0"}, clear=True):
            key = secrets_config.get_stripe_key()
            self.assertEqual(key, "sk_test_456")
    
    def test_get_stripe_key_prefers_stripe_secret_key(self):
        """Test that STRIPE_SECRET_KEY takes precedence over STRIPE_API_KEY."""
        with patch.dict(os.environ, {
            "STRIPE_SECRET_KEY": "sk_test_secret",
            "STRIPE_API_KEY": "sk_test_api",
            "PRODUCTION": "0"
        }, clear=True):
            key = secrets_config.get_stripe_key()
            self.assertEqual(key, "sk_test_secret")
    
    def test_get_stripe_key_non_production_missing_key_returns_empty(self):
        """Test that missing key in non-production returns empty string with warning."""
        with patch.dict(os.environ, {"PRODUCTION": "0"}, clear=True):
            with self.assertLogs('core.secrets_config', level='WARNING') as cm:
                key = secrets_config.get_stripe_key()
                self.assertEqual(key, "")
                self.assertTrue(any("Stripe API key is not set" in msg for msg in cm.output))
                self.assertTrue(any("non-production" in msg for msg in cm.output))
    
    def test_get_stripe_key_production_missing_key_raises(self):
        """Test that missing key in production raises RuntimeError."""
        with patch.dict(os.environ, {"PRODUCTION": "1"}, clear=True):
            with self.assertRaises(RuntimeError) as cm:
                secrets_config.get_stripe_key()
            self.assertIn("Stripe API key is not set", str(cm.exception))
            self.assertIn("production", str(cm.exception))
    
    def test_get_stripe_key_explicit_production_true(self):
        """Test explicit production=True parameter raises on missing key."""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as cm:
                secrets_config.get_stripe_key(production=True)
            self.assertIn("Stripe API key is not set", str(cm.exception))
    
    def test_get_stripe_key_explicit_production_false(self):
        """Test explicit production=False parameter returns empty on missing key."""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertLogs('core.secrets_config', level='WARNING') as cm:
                key = secrets_config.get_stripe_key(production=False)
                self.assertEqual(key, "")
                self.assertTrue(any("non-production" in msg for msg in cm.output))
    
    def test_get_stripe_key_production_with_key_succeeds(self):
        """Test that production mode with key set returns the key."""
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_live_789", "PRODUCTION": "1"}, clear=True):
            key = secrets_config.get_stripe_key()
            self.assertEqual(key, "sk_live_789")
    
    def test_production_env_var_parsing(self):
        """Test PRODUCTION env var is correctly parsed as boolean."""
        # Test "0" is False
        with patch.dict(os.environ, {"PRODUCTION": "0"}, clear=True):
            with self.assertLogs('core.secrets_config', level='WARNING'):
                key = secrets_config.get_stripe_key()
                self.assertEqual(key, "")
        
        # Test "1" is True
        with patch.dict(os.environ, {"PRODUCTION": "1"}, clear=True):
            with self.assertRaises(RuntimeError):
                secrets_config.get_stripe_key()
        
        # Test missing defaults to False
        with patch.dict(os.environ, {}, clear=True):
            with self.assertLogs('core.secrets_config', level='WARNING'):
                key = secrets_config.get_stripe_key()
                self.assertEqual(key, "")
