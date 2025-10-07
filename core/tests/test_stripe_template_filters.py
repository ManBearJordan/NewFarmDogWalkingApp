"""Tests for Stripe template filters."""
import pytest
from unittest.mock import patch
from core.templatetags.stripe_filters import stripe_payment_url


def test_stripe_payment_url_with_valid_pi():
    """Test stripe_payment_url filter with a valid payment intent ID."""
    with patch('core.stripe_key_manager.get_key_status') as mock_status:
        mock_status.return_value = {
            'configured': True,
            'mode': 'env',
            'test_or_live': 'test'
        }
        
        url = stripe_payment_url("pi_test_123456789")
        assert url == "https://dashboard.stripe.com/test/payments/pi_test_123456789"


def test_stripe_payment_url_with_live_mode():
    """Test stripe_payment_url filter with live mode."""
    with patch('core.stripe_key_manager.get_key_status') as mock_status:
        mock_status.return_value = {
            'configured': True,
            'mode': 'env',
            'test_or_live': 'live'
        }
        
        url = stripe_payment_url("pi_live_987654321")
        assert url == "https://dashboard.stripe.com/payments/pi_live_987654321"


def test_stripe_payment_url_with_none():
    """Test stripe_payment_url filter with None returns fallback."""
    url = stripe_payment_url(None)
    assert url == "#"


def test_stripe_payment_url_with_empty_string():
    """Test stripe_payment_url filter with empty string returns fallback."""
    url = stripe_payment_url("")
    assert url == "#"


def test_stripe_payment_url_handles_exceptions():
    """Test stripe_payment_url filter handles exceptions gracefully."""
    with patch('core.stripe_integration.payment_intent_dashboard_url') as mock_url:
        mock_url.side_effect = Exception("Test error")
        
        url = stripe_payment_url("pi_test_error")
        # Should fallback to test mode URL
        assert url == "https://dashboard.stripe.com/test/payments/pi_test_error"
