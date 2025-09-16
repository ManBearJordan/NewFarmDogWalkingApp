#!/usr/bin/env python3

"""
Test script to validate customer name handling fixes.
This tests the specific issues mentioned in the problem statement.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from stripe_integration import list_subscriptions


class TestCustomerNameFixes(unittest.TestCase):
    """Test customer name handling improvements"""
    
    @patch('stripe_integration._api')
    def test_customer_name_fallback_to_email(self, mock_api):
        """Test that customer name falls back to email when name is missing"""
        
        # Mock Stripe subscription with missing customer name but email present
        mock_stripe_api = Mock()
        mock_api.return_value = mock_stripe_api
        
        mock_subscription = Mock()
        mock_subscription.__dict__ = {
            'id': 'sub_test123',
            'status': 'active',
            'customer': {
                'id': 'cus_test456',
                'name': None,  # Missing customer name
                'email': 'testuser@example.com'
            },
            'items': {'data': []},
            'latest_invoice': None,
            'current_period_end': 1234567890
        }
        
        # Mock dict() conversion
        def mock_dict(obj):
            return obj.__dict__
        
        mock_stripe_api.Subscription.list.return_value.auto_paging_iter.return_value = [mock_subscription]
        
        with patch('builtins.dict', mock_dict):
            subscriptions = list_subscriptions(limit=1)
        
        # Verify customer name falls back to email
        self.assertEqual(len(subscriptions), 1)
        self.assertEqual(subscriptions[0]['customer_name'], 'testuser@example.com')
        self.assertEqual(subscriptions[0]['customer_email'], 'testuser@example.com')
    
    @patch('stripe_integration._api')
    def test_customer_name_fetch_from_stripe_api(self, mock_api):
        """Test that customer name is fetched from Stripe API when missing from subscription"""
        
        mock_stripe_api = Mock()
        mock_api.return_value = mock_stripe_api
        
        # Mock customer object that will be fetched
        mock_customer_obj = Mock()
        mock_customer_obj.name = "John Doe"
        mock_customer_obj.email = "john@example.com"
        mock_stripe_api.Customer.retrieve.return_value = mock_customer_obj
        
        mock_subscription = Mock()
        mock_subscription.__dict__ = {
            'id': 'sub_test123',
            'status': 'active',
            'customer': {
                'id': 'cus_test456',
                'name': None,  # Missing customer name
                'email': None   # Also missing email
            },
            'items': {'data': []},
            'latest_invoice': None,
            'current_period_end': 1234567890
        }
        
        # Mock dict() conversion
        def mock_dict(obj):
            return obj.__dict__
        
        mock_stripe_api.Subscription.list.return_value.auto_paging_iter.return_value = [mock_subscription]
        
        with patch('builtins.dict', mock_dict):
            subscriptions = list_subscriptions(limit=1)
        
        # Verify customer name was fetched from Stripe Customer API and formatted properly with email
        self.assertEqual(len(subscriptions), 1)
        self.assertEqual(subscriptions[0]['customer_name'], 'John Doe (john@example.com)')  # Updated per requirements
        mock_stripe_api.Customer.retrieve.assert_called_once_with('cus_test456')
    
    @patch('stripe_integration._api')
    def test_stripe_api_error_fallback(self, mock_api):
        """Test that Stripe API errors fall back to Customer {id} (Stripe API error) instead of Unknown Customer"""
        
        mock_stripe_api = Mock()
        mock_api.return_value = mock_stripe_api
        
        # Mock customer fetch that fails
        mock_stripe_api.Customer.retrieve.side_effect = Exception("API Error")
        
        mock_subscription = Mock()
        mock_subscription.__dict__ = {
            'id': 'sub_test123',
            'status': 'active',
            'customer': {
                'id': 'cus_test456',
                'name': None,  # Missing customer name
                'email': None   # Also missing email
            },
            'items': {'data': []},
            'latest_invoice': None,
            'current_period_end': 1234567890
        }
        
        # Mock dict() conversion
        def mock_dict(obj):
            return obj.__dict__
        
        mock_stripe_api.Subscription.list.return_value.auto_paging_iter.return_value = [mock_subscription]
        
        with patch('builtins.dict', mock_dict):
            subscriptions = list_subscriptions(limit=1)
        
        # Verify fallback behavior per requirements: "Customer {id} (Stripe API error)" instead of "Unknown Customer"
        self.assertEqual(len(subscriptions), 1)
        self.assertEqual(subscriptions[0]['customer_name'], 'Customer cus_test456 (Stripe API error)')  # Updated per requirements
    
    @patch('stripe_integration._api')
    def test_customer_name_with_valid_name(self, mock_api):
        """Test that valid customer name is used when present"""
        
        mock_stripe_api = Mock()
        mock_api.return_value = mock_stripe_api
        
        mock_subscription = Mock()
        mock_subscription.__dict__ = {
            'id': 'sub_test123',
            'status': 'active',
            'customer': {
                'id': 'cus_test456',
                'name': 'Jane Smith',  # Valid customer name
                'email': 'jane@example.com'
            },
            'items': {'data': []},
            'latest_invoice': None,
            'current_period_end': 1234567890
        }
        
        # Mock dict() conversion
        def mock_dict(obj):
            return obj.__dict__
        
        mock_stripe_api.Subscription.list.return_value.auto_paging_iter.return_value = [mock_subscription]
        
        with patch('builtins.dict', mock_dict):
            subscriptions = list_subscriptions(limit=1)
        
        # Verify valid customer name is used and formatted properly with email 
        self.assertEqual(len(subscriptions), 1)
        self.assertEqual(subscriptions[0]['customer_name'], 'Jane Smith (jane@example.com)')  # Updated per requirements
        self.assertEqual(subscriptions[0]['customer_email'], 'jane@example.com')


if __name__ == '__main__':
    unittest.main()