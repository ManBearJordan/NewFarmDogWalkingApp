#!/usr/bin/env python3

"""
Test script to validate the list_active_subscriptions_from_stripe helper function.

This tests both auto_paging_iter and .data shapes returned from stripe.Subscription.list.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock


class TestListSubscriptionsHelper(unittest.TestCase):
    """Test the robust list_active_subscriptions_from_stripe helper function"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock subscription data
        self.mock_subscription_data = {
            'id': 'sub_test123',
            'status': 'active',
            'customer': {
                'id': 'cus_test456',
                'email': 'test@example.com',
                'name': 'Test Customer'
            },
            'items': {
                'data': [
                    {
                        'price': {
                            'id': 'price_test789',
                            'product': 'prod_testABC'
                        }
                    }
                ]
            }
        }
    
    @patch('log_utils.get_subscription_logger')
    @patch('log_utils.log_subscription_error')
    @patch('stripe_integration.stripe')
    def test_auto_paging_iter_response_shape(self, mock_stripe, mock_log_error, mock_logger):
        """Test handling of auto_paging_iter response shape"""
        from stripe_integration import list_active_subscriptions_from_stripe
        
        # Mock response with auto_paging_iter method
        mock_response = Mock()
        mock_response.auto_paging_iter = Mock(return_value=[self.mock_subscription_data])
        mock_response.data = None  # Should not be used when auto_paging_iter is available
        
        mock_stripe.Subscription.list.return_value = mock_response
        
        result = list_active_subscriptions_from_stripe(limit=100)
        
        # Verify correct iteration method was used
        mock_response.auto_paging_iter.assert_called_once()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 'sub_test123')
    
    @patch('log_utils.get_subscription_logger')
    @patch('log_utils.log_subscription_error')
    @patch('stripe_integration.stripe')
    def test_data_attribute_response_shape(self, mock_stripe, mock_log_error, mock_logger):
        """Test handling of .data attribute response shape"""
        from stripe_integration import list_active_subscriptions_from_stripe
        
        # Mock response with data attribute but no auto_paging_iter
        mock_response = Mock()
        mock_response.auto_paging_iter = None  # Not callable
        mock_response.data = [self.mock_subscription_data]
        
        mock_stripe.Subscription.list.return_value = mock_response
        
        result = list_active_subscriptions_from_stripe(limit=100)
        
        # Verify correct fallback to .data was used
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 'sub_test123')
    
    @patch('log_utils.get_subscription_logger')
    @patch('log_utils.log_subscription_error')
    @patch('stripe_integration.stripe')
    def test_list_response_shape_fallback(self, mock_stripe, mock_log_error, mock_logger):
        """Test handling of list() response shape as final fallback"""
        from stripe_integration import list_active_subscriptions_from_stripe
        
        # Mock response that is directly iterable
        mock_response = [self.mock_subscription_data]
        
        mock_stripe.Subscription.list.return_value = mock_response
        
        result = list_active_subscriptions_from_stripe(limit=100)
        
        # Verify list fallback worked
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 'sub_test123')
    
    @patch('log_utils.get_subscription_logger')
    @patch('log_utils.log_subscription_error')
    @patch('stripe_integration.stripe')
    def test_stripe_api_error_handling(self, mock_stripe, mock_log_error, mock_logger):
        """Test proper error handling when Stripe API call fails"""
        from stripe_integration import list_active_subscriptions_from_stripe
        
        # Mock Stripe API to raise an exception
        mock_stripe.Subscription.list.side_effect = Exception("API Error")
        
        result = list_active_subscriptions_from_stripe(limit=100)
        
        # Verify error was logged and empty list returned
        mock_log_error.assert_called_once()
        self.assertEqual(result, [])
    
    @patch('log_utils.get_subscription_logger')
    @patch('log_utils.log_subscription_error')  
    @patch('stripe_integration.stripe')
    def test_iteration_error_handling(self, mock_stripe, mock_log_error, mock_logger):
        """Test proper error handling when iteration fails"""
        from stripe_integration import list_active_subscriptions_from_stripe
        
        # Mock response where auto_paging_iter raises an exception
        mock_response = Mock()
        mock_response.auto_paging_iter.side_effect = Exception("Iteration Error")
        mock_response.data = [self.mock_subscription_data]  # Should fall back to this
        
        mock_stripe.Subscription.list.return_value = mock_response
        
        result = list_active_subscriptions_from_stripe(limit=100)
        
        # Verify fallback to .data worked
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 'sub_test123')
    
    @patch('log_utils.get_subscription_logger')
    @patch('log_utils.log_subscription_error')
    @patch('stripe_integration.stripe')
    def test_expand_parameter_passing(self, mock_stripe, mock_log_error, mock_logger):
        """Test that expand parameters are correctly passed to Stripe API"""
        from stripe_integration import list_active_subscriptions_from_stripe
        
        mock_response = Mock()
        mock_response.auto_paging_iter = Mock(return_value=[])
        mock_stripe.Subscription.list.return_value = mock_response
        
        expand_params = ['data.customer', 'data.items.data.price']
        list_active_subscriptions_from_stripe(limit=50, expand=expand_params)
        
        # Verify correct parameters were passed to Stripe
        mock_stripe.Subscription.list.assert_called_once_with(
            limit=50,
            expand=expand_params
        )
    
    @patch('log_utils.get_subscription_logger')  
    @patch('log_utils.log_subscription_error')
    @patch('stripe_integration.stripe')
    def test_unexpected_response_shape(self, mock_stripe, mock_log_error, mock_logger):
        """Test handling of unexpected response shapes"""
        from stripe_integration import list_active_subscriptions_from_stripe
        
        # Mock response that has neither auto_paging_iter nor data, and isn't iterable
        mock_response = Mock()
        mock_response.auto_paging_iter = None
        mock_response.data = None
        # Make list() fail on the mock response
        mock_response.__iter__ = Mock(side_effect=Exception("Not iterable"))
        
        mock_stripe.Subscription.list.return_value = mock_response
        
        result = list_active_subscriptions_from_stripe(limit=100)
        
        # Should return empty list and log warning
        self.assertEqual(result, [])
        # Verify warning was logged
        mock_logger.return_value.warning.assert_called()


if __name__ == '__main__':
    unittest.main()