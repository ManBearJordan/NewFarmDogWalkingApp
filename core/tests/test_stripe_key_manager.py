import os
import sys
from unittest.mock import patch
from django.test import TestCase, override_settings
from core import stripe_key_manager as m

class StripeKeyManagerNewTest(TestCase):
    def setUp(self):
        """Reset memory state before each test"""
        with m._LOCK:
            m._MEM.clear()

    @override_settings(USE_KEYRING=False)
    def test_get_key_env_only_empty(self):
        """Test get_key with no environment variable"""
        with patch.dict(os.environ, {}, clear=True):
            key = m.get_stripe_key()
            self.assertIsNone(key)
            st = m.get_key_status()
            self.assertIsNone(st["mode"])
            self.assertFalse(st["configured"])

    @override_settings(USE_KEYRING=False)
    def test_get_key_env_only_with_key(self):
        """Test get_key with environment variable set"""
        with patch.dict(os.environ, {"STRIPE_API_KEY": "sk_test_from_env"}, clear=True):
            key = m.get_stripe_key()
            self.assertEqual(key, "sk_test_from_env")
            st = m.get_key_status()
            self.assertEqual(st["mode"], "env")
            self.assertTrue(st["configured"])
            self.assertEqual(st["test_or_live"], "test")

    @override_settings(USE_KEYRING=False)
    def test_memory_override_without_keyring(self):
        """Test memory override when keyring is disabled"""
        with patch.dict(os.environ, {}, clear=True):
            m.update_stripe_key("sk_test_mem")
            self.assertEqual(m.get_stripe_key(), "sk_test_mem")
            st = m.get_key_status()
            self.assertEqual(st["mode"], "memory")
            self.assertTrue(st["configured"])
            self.assertEqual(st["test_or_live"], "test")

    @override_settings(USE_KEYRING=True, KEYRING_SERVICE_NAME="NFDWTest")
    def test_keyring_fallback(self):
        """Test keyring functionality with fake keyring"""
        # Create fake keyring module
        class FakeKR:
            store = {}
            @classmethod
            def get_password(cls, svc, user): return cls.store.get((svc, user))
            @classmethod
            def set_password(cls, svc, user, value): cls.store[(svc, user)] = value
            @classmethod
            def delete_password(cls, svc, user): cls.store.pop((svc, user), None)
        
        with patch.dict(os.environ, {}, clear=True):
            with patch.dict(sys.modules, {"keyring": FakeKR}):
                m.update_stripe_key("sk_live_keyring")
                self.assertEqual(m.get_stripe_key(), "sk_live_keyring")
                st = m.get_key_status()
                self.assertEqual(st["mode"], "keyring")
                self.assertTrue(st["configured"])
                self.assertEqual(st["test_or_live"], "live")

    @override_settings(USE_KEYRING=False)
    def test_priority_order(self):
        """Test that memory override takes priority over env"""
        with patch.dict(os.environ, {"STRIPE_API_KEY": "sk_test_env"}, clear=True):
            # First, env key should be returned
            self.assertEqual(m.get_stripe_key(), "sk_test_env")
            
            # Set memory override
            m.update_stripe_key("sk_test_memory")
            
            # Memory should take priority now
            self.assertEqual(m.get_stripe_key(), "sk_test_memory")
            st = m.get_key_status()
            self.assertEqual(st["mode"], "memory")

    @override_settings(USE_KEYRING=False)
    def test_clear_key(self):
        """Test clearing a key sets it to None"""
        with patch.dict(os.environ, {}, clear=True):
            m.update_stripe_key("sk_test_temp")
            self.assertIsNotNone(m.get_stripe_key())
            
            m.update_stripe_key(None)
            self.assertIsNone(m.get_stripe_key())
            st = m.get_key_status()
            self.assertFalse(st["configured"])