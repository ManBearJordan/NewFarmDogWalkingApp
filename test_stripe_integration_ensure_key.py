"""
Test the new ensure_stripe_key functionality in stripe_integration.py

This test module verifies that the Stripe key validation and retry logic
works as expected, including handling of authentication errors and network issues.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, Mock
from stripe.error import AuthenticationError

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(__file__))

class TestStripeIntegrationEnsureKey(unittest.TestCase):
    """Test cases for the new ensure_stripe_key function in stripe_integration.py"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_key = "sk_test_51234567890abcdefghijklmnopqrstuvwxyz"
        self.live_key = "sk_live_51234567890abcdefghijklmnopqrstuvwxyz"
        self.invalid_key = "sk_test_invalid123"
        
        # Clear environment variables that might interfere
        for key in ['STRIPE_SECRET_KEY', 'STRIPE_API_KEY']:
            if key in os.environ:
                del os.environ[key]
                
        # Clear any cached modules
        modules_to_clear = ['stripe_integration', 'stripe']
        for module in modules_to_clear:
            if module in sys.modules:
                del sys.modules[module]
    
    def tearDown(self):
        """Clean up after tests"""
        # Clear environment variables
        for key in ['STRIPE_SECRET_KEY', 'STRIPE_API_KEY']:
            if key in os.environ:
                del os.environ[key]
                
        # Clear any cached modules for clean slate
        modules_to_clear = ['stripe_integration', 'stripe']
        for module in modules_to_clear:
            if module in sys.modules:
                del sys.modules[module]
    
    @patch('stripe_key_manager.prompt_for_stripe_key')  
    @patch('stripe_key_manager.set_stripe_key')
    @patch('stripe_key_manager.get_stripe_key')
    @patch('stripe.Customer.list')
    def test_ensure_stripe_key_existing_valid_key(self, mock_customer_list, mock_get_key, mock_set_key, mock_prompt):
        """Test ensure_stripe_key with an existing valid key"""
        # Setup mocks
        mock_get_key.return_value = self.test_key
        mock_customer_list.return_value = MagicMock()  # Successful API call
        
        # Import will trigger ensure_stripe_key
        import stripe_integration
        
        # Verify the key was used
        self.assertEqual(stripe_integration.stripe.api_key, self.test_key)
        mock_get_key.assert_called_once()
        mock_customer_list.assert_called_once_with(limit=1)
        mock_prompt.assert_not_called()  # Shouldn't prompt if key exists and works
    
    @patch('stripe_key_manager.prompt_for_stripe_key')  
    @patch('stripe_key_manager.set_stripe_key')
    @patch('stripe_key_manager.get_stripe_key')
    @patch('stripe.Customer.list')
    def test_ensure_stripe_key_no_key_prompt_success(self, mock_customer_list, mock_get_key, mock_set_key, mock_prompt):
        """Test ensure_stripe_key when no key exists, user provides valid key"""
        # Setup mocks
        mock_get_key.return_value = ""  # No existing key
        mock_prompt.return_value = self.test_key  # User provides key
        mock_set_key.return_value = True  # Key stored successfully
        mock_customer_list.return_value = MagicMock()  # Valid key
        
        # Import will trigger ensure_stripe_key
        import stripe_integration
        
        # Verify the workflow
        mock_get_key.assert_called_once()
        mock_prompt.assert_called_once()
        mock_set_key.assert_called_once_with(self.test_key)
        self.assertEqual(stripe_integration.stripe.api_key, self.test_key)
        mock_customer_list.assert_called_once_with(limit=1)
    
    @patch('stripe_key_manager.prompt_for_stripe_key')  
    @patch('stripe_key_manager.set_stripe_key')
    @patch('stripe_key_manager.get_stripe_key')
    def test_ensure_stripe_key_no_key_prompt_cancelled(self, mock_get_key, mock_set_key, mock_prompt):
        """Test ensure_stripe_key when no key exists and user cancels prompt"""
        # Setup mocks
        mock_get_key.return_value = ""  # No existing key
        mock_prompt.return_value = None  # User cancels
        
        # Import will trigger ensure_stripe_key
        import stripe_integration
        
        # Verify the workflow
        mock_get_key.assert_called_once()
        mock_prompt.assert_called_once()
        mock_set_key.assert_not_called()  # No key to store
        self.assertEqual(stripe_integration.stripe.api_key, "")
    
    @patch('stripe_key_manager.prompt_for_stripe_key')  
    @patch('stripe_key_manager.set_stripe_key')
    @patch('stripe_key_manager.get_stripe_key')
    @patch('stripe.Customer.list')
    def test_ensure_stripe_key_invalid_key_retry_success(self, mock_customer_list, mock_get_key, mock_set_key, mock_prompt):
        """Test ensure_stripe_key when existing key is invalid, retry with valid key"""
        # Setup mocks
        mock_get_key.return_value = self.invalid_key  # Invalid existing key
        mock_prompt.return_value = self.test_key  # User provides valid key
        mock_set_key.return_value = True  # New key stored successfully
        mock_customer_list.side_effect = AuthenticationError("Invalid API key")
        
        # Import will trigger ensure_stripe_key
        import stripe_integration
        
        # Verify the workflow
        mock_get_key.assert_called_once()
        mock_customer_list.assert_called_once_with(limit=1)
        mock_prompt.assert_called_once()  # Prompted for new key
        mock_set_key.assert_called_once_with(self.test_key)
        self.assertEqual(stripe_integration.stripe.api_key, self.test_key)
    
    @patch('stripe_key_manager.prompt_for_stripe_key')  
    @patch('stripe_key_manager.set_stripe_key')
    @patch('stripe_key_manager.get_stripe_key')
    @patch('stripe.Customer.list')
    def test_ensure_stripe_key_invalid_key_retry_cancelled(self, mock_customer_list, mock_get_key, mock_set_key, mock_prompt):
        """Test ensure_stripe_key when existing key is invalid and user cancels retry"""
        # Setup mocks
        mock_get_key.return_value = self.invalid_key  # Invalid existing key
        mock_prompt.return_value = None  # User cancels prompt
        mock_customer_list.side_effect = AuthenticationError("Invalid API key")
        
        # Import will trigger ensure_stripe_key
        import stripe_integration
        
        # Verify the workflow
        mock_get_key.assert_called_once()
        mock_customer_list.assert_called_once_with(limit=1)
        mock_prompt.assert_called_once()  # Prompted for new key
        mock_set_key.assert_not_called()  # No new key to store
        # Key should remain as the old invalid one since user cancelled
        self.assertEqual(stripe_integration.stripe.api_key, self.invalid_key)
    
    @patch('stripe_key_manager.get_stripe_key')
    @patch('stripe.Customer.list')
    def test_ensure_stripe_key_network_error_handling(self, mock_customer_list, mock_get_key):
        """Test ensure_stripe_key handles network errors gracefully (doesn't prompt for new key)"""
        # Setup mocks
        mock_get_key.return_value = self.test_key  # Valid key
        # Simulate SSL/network error (not authentication error)
        mock_customer_list.side_effect = Exception("SSL: CERTIFICATE_VERIFY_FAILED")
        
        # Import will trigger ensure_stripe_key  
        import stripe_integration
        
        # Verify network error was handled gracefully
        mock_get_key.assert_called_once()
        mock_customer_list.assert_called_once_with(limit=1)
        # Key should be set despite network error
        self.assertEqual(stripe_integration.stripe.api_key, self.test_key)
    
    @patch('stripe_key_manager.prompt_for_stripe_key')
    @patch('stripe_key_manager.set_stripe_key')
    @patch('stripe_key_manager.get_stripe_key')
    @patch('stripe.Customer.list')
    def test_ensure_stripe_key_auth_like_error_in_message(self, mock_customer_list, mock_get_key, mock_set_key, mock_prompt):
        """Test ensure_stripe_key treats errors with 'authentication' in message as auth errors"""
        # Setup mocks
        mock_get_key.return_value = self.test_key
        mock_prompt.return_value = self.live_key  # User provides new key
        mock_set_key.return_value = True
        # Simulate error that contains 'authentication' but isn't AuthenticationError
        mock_customer_list.side_effect = Exception("Request failed: authentication failed")
        
        # Import will trigger ensure_stripe_key
        import stripe_integration
        
        # Verify it was treated as authentication error
        mock_get_key.assert_called_once()
        mock_customer_list.assert_called_once_with(limit=1)
        mock_prompt.assert_called_once()  # Should prompt for new key
        mock_set_key.assert_called_once_with(self.live_key)
        self.assertEqual(stripe_integration.stripe.api_key, self.live_key)

    def test_ensure_stripe_key_function_exists(self):
        """Test that the ensure_stripe_key function exists and can be called directly"""
        # Mock the dependencies to avoid prompts
        with patch('stripe_key_manager.get_stripe_key', return_value=self.test_key), \
             patch('stripe.Customer.list', return_value=MagicMock()):
            
            import stripe_integration
            
            # Test that the function exists and can be called
            self.assertTrue(hasattr(stripe_integration, 'ensure_stripe_key'))
            self.assertTrue(callable(stripe_integration.ensure_stripe_key))
            
            # Test calling it directly
            stripe_integration.ensure_stripe_key()
            self.assertEqual(stripe_integration.stripe.api_key, self.test_key)


if __name__ == '__main__':
    unittest.main(verbosity=2)