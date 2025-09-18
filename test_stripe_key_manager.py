"""
Test stripe_key_manager functionality

This test module verifies that the secure Stripe key storage and retrieval
system works as expected, both with and without the keyring library.
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import sys

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(__file__))

import stripe_key_manager


class TestStripeKeyManager(unittest.TestCase):
    """Test cases for stripe_key_manager module"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_key = "sk_test_51234567890abcdefghijklmnopqrstuvwxyz"
        self.live_key = "sk_live_51234567890abcdefghijklmnopqrstuvwxyz"
        
        # Clear environment variables that might interfere
        for key in ['STRIPE_SECRET_KEY', 'STRIPE_API_KEY']:
            if key in os.environ:
                del os.environ[key]
    
    def tearDown(self):
        """Clean up after tests"""
        # Clear environment variables
        for key in ['STRIPE_SECRET_KEY', 'STRIPE_API_KEY']:
            if key in os.environ:
                del os.environ[key]
    
    def test_get_stripe_key_from_env_variable(self):
        """Test retrieving key from environment variable"""
        os.environ['STRIPE_SECRET_KEY'] = self.test_key
        key = stripe_key_manager.get_stripe_key()
        self.assertEqual(key, self.test_key)
    
    def test_get_stripe_key_from_alternative_env_variable(self):
        """Test retrieving key from alternative environment variable"""
        os.environ['STRIPE_API_KEY'] = self.test_key
        key = stripe_key_manager.get_stripe_key()
        self.assertEqual(key, self.test_key)
    
    def test_get_stripe_key_no_key_available(self):
        """Test behavior when no key is available"""
        key = stripe_key_manager.get_stripe_key()
        self.assertEqual(key, "")
    
    def test_set_stripe_key_validation(self):
        """Test key validation in set_stripe_key"""
        # Test empty key
        result = stripe_key_manager.set_stripe_key("")
        self.assertFalse(result)
        
        # Test None key
        result = stripe_key_manager.set_stripe_key(None)
        self.assertFalse(result)
    
    @patch('stripe_key_manager.KEYRING_AVAILABLE', True)
    @patch('stripe_key_manager.keyring')
    def test_set_stripe_key_with_keyring(self, mock_keyring):
        """Test storing key with keyring available"""
        mock_keyring.set_password.return_value = None
        
        result = stripe_key_manager.set_stripe_key(self.test_key)
        self.assertTrue(result)
        
        mock_keyring.set_password.assert_called_once_with(
            stripe_key_manager.SERVICE_NAME,
            stripe_key_manager.KEY_NAME,
            self.test_key
        )
    
    @patch('stripe_key_manager.KEYRING_AVAILABLE', True)
    @patch('stripe_key_manager.keyring')
    def test_get_stripe_key_with_keyring(self, mock_keyring):
        """Test retrieving key with keyring available"""
        mock_keyring.get_password.return_value = self.test_key
        
        key = stripe_key_manager.get_stripe_key()
        self.assertEqual(key, self.test_key)
        
        mock_keyring.get_password.assert_called_once_with(
            stripe_key_manager.SERVICE_NAME,
            stripe_key_manager.KEY_NAME
        )
    
    @patch('stripe_key_manager.KEYRING_AVAILABLE', True)
    @patch('stripe_key_manager.keyring')
    def test_delete_stripe_key_with_keyring(self, mock_keyring):
        """Test deleting key with keyring available"""
        mock_keyring.delete_password.return_value = None
        
        result = stripe_key_manager.delete_stripe_key()
        self.assertTrue(result)
        
        mock_keyring.delete_password.assert_called_once_with(
            stripe_key_manager.SERVICE_NAME,
            stripe_key_manager.KEY_NAME
        )
    
    def test_get_key_status_no_key(self):
        """Test status when no key is available"""
        status = stripe_key_manager.get_key_status()
        
        # Test the essential fields, allowing flexibility for keyring vs environment fallback
        self.assertFalse(status["key_stored"])
        self.assertIsNone(status["key_type"])
        self.assertEqual(status["service_name"], stripe_key_manager.SERVICE_NAME)
        self.assertEqual(status["key_name"], stripe_key_manager.KEY_NAME)
        self.assertIn("keyring_available", status)
        self.assertIn("gui_available", status)
        self.assertIn("storage_method", status)
    
    def test_get_key_status_with_test_key(self):
        """Test status with a test key"""
        os.environ['STRIPE_SECRET_KEY'] = self.test_key
        status = stripe_key_manager.get_key_status()
        
        self.assertTrue(status["key_stored"])
        self.assertEqual(status["key_type"], "test")
    
    def test_get_key_status_with_live_key(self):
        """Test status with a live key"""
        os.environ['STRIPE_SECRET_KEY'] = self.live_key
        status = stripe_key_manager.get_key_status()
        
        self.assertTrue(status["key_stored"])
        self.assertEqual(status["key_type"], "live")
    
    @patch('builtins.input', return_value=None)
    def test_prompt_for_stripe_key_skip(self, mock_input):
        """Test skipping key prompt"""
        mock_input.return_value = ""
        result = stripe_key_manager.prompt_for_stripe_key()
        self.assertIsNone(result)
    
    @patch('builtins.input')
    def test_prompt_for_stripe_key_success(self, mock_input):
        """Test successful key prompt"""
        mock_input.return_value = self.test_key
        result = stripe_key_manager.prompt_for_stripe_key()
        self.assertEqual(result, self.test_key)
    
    @patch('stripe_key_manager.prompt_for_stripe_key')
    @patch('stripe_key_manager.set_stripe_key')
    def test_ensure_stripe_key_new_key(self, mock_set_key, mock_prompt):
        """Test ensure_stripe_key when no key exists"""
        mock_prompt.return_value = self.test_key
        mock_set_key.return_value = True
        
        result = stripe_key_manager.ensure_stripe_key()
        self.assertEqual(result, self.test_key)
        
        mock_prompt.assert_called_once()
        mock_set_key.assert_called_once_with(self.test_key)
    
    def test_ensure_stripe_key_existing_key(self):
        """Test ensure_stripe_key when key already exists"""
        os.environ['STRIPE_SECRET_KEY'] = self.test_key
        
        result = stripe_key_manager.ensure_stripe_key()
        self.assertEqual(result, self.test_key)


class TestStripeIntegrationUpdate(unittest.TestCase):
    """Test that stripe_integration.py works with the new key manager"""
    
    def test_stripe_integration_imports_successfully(self):
        """Test that stripe_integration can import with the new key manager"""
        os.environ['STRIPE_SECRET_KEY'] = "sk_test_example"
        
        try:
            import stripe_integration
            # If we get here without exception, the import worked
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"stripe_integration failed to import: {e}")
    
    def test_stripe_api_key_is_set(self):
        """Test that the Stripe API key is properly set"""
        test_key = "sk_test_integration_test"
        os.environ['STRIPE_SECRET_KEY'] = test_key
        
        # Import fresh module
        if 'stripe_integration' in sys.modules:
            del sys.modules['stripe_integration']
        if 'stripe' in sys.modules:
            del sys.modules['stripe']
        
        import stripe_integration
        import stripe
        
        # Check that the API key was set
        self.assertEqual(stripe.api_key, test_key)


if __name__ == '__main__':
    unittest.main(verbosity=2)