import os
import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from core import subscription_sync


class SubscriptionSyncIntegrationTest(TestCase):
    """Tests for subscription_sync integration with secrets_config."""
    
    @patch('core.subscription_sync.list_active_subscriptions')
    def test_get_active_subscriptions_production_missing_key_returns_empty(self, mock_list):
        """Test that missing key in production returns empty list and logs error."""
        with patch.dict(os.environ, {"PRODUCTION": "1"}, clear=True):
            with self.assertLogs('core.subscription_sync', level='ERROR') as cm:
                result = subscription_sync._get_active_subscriptions(90)
                self.assertEqual(result, [])
                # Check that [Stripe] prefix is in the error log
                self.assertTrue(any("[Stripe]" in msg for msg in cm.output))
    
    @patch('core.subscription_sync.list_active_subscriptions')
    def test_get_active_subscriptions_non_production_missing_key_uses_fake(self, mock_list):
        """Test that missing key in non-production uses fake data with info log."""
        with patch.dict(os.environ, {"PRODUCTION": "0"}, clear=True):
            with self.assertLogs('core.subscription_sync', level='INFO') as cm:
                result = subscription_sync._get_active_subscriptions(90)
                # Should return fake subscriptions
                self.assertGreater(len(result), 0)
                # Check that [Stripe] prefix is in the info log
                self.assertTrue(any("[Stripe]" in msg and "sample" in msg for msg in cm.output))
    
    @patch('core.subscription_sync.list_active_subscriptions')
    def test_get_active_subscriptions_with_key_calls_stripe(self, mock_list):
        """Test that with a valid key, Stripe API is called."""
        # Mock the Stripe API response
        mock_sub = MagicMock()
        mock_sub.id = 'sub_test_123'
        mock_sub.status = 'active'
        mock_sub.current_period_start = 1234567890
        mock_sub.current_period_end = 1234567900
        mock_sub.plan.interval = 'month'
        mock_sub.plan.interval_count = 1
        mock_sub.metadata = {}
        
        mock_response = MagicMock()
        mock_response.auto_paging_iter.return_value = [mock_sub]
        mock_list.return_value = mock_response
        
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_123", "PRODUCTION": "0"}, clear=True):
            result = subscription_sync._get_active_subscriptions(90)
            # Should call Stripe API
            mock_list.assert_called_once()
            # Should return the subscription data
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['id'], 'sub_test_123')
    
    @patch('core.subscription_sync._get_active_subscriptions')
    def test_sync_subscriptions_logs_errors_with_prefix(self, mock_get_subs):
        """Test that sync function logs errors with [Sync] prefix."""
        # Return a subscription that will cause an error
        mock_get_subs.return_value = [
            {'id': 'sub_error', 'plan': {'interval': 'month', 'interval_count': 1}}
        ]
        
        # Mock _expand_subscription_occurrences to raise an error
        with patch('core.subscription_sync._expand_subscription_occurrences') as mock_expand:
            mock_expand.side_effect = Exception("Test error")
            
            with self.assertLogs('core.subscription_sync', level='ERROR') as cm:
                result = subscription_sync.sync_subscriptions_to_bookings_and_calendar(90)
                # Should have errors
                self.assertGreater(result['errors'], 0)
                # Check that [Sync] prefix is in the error log
                self.assertTrue(any("[Sync]" in msg and "Error materializing" in msg for msg in cm.output))
                self.assertTrue(any("[Sync]" in msg and "Completed with" in msg and "errors" in msg for msg in cm.output))
