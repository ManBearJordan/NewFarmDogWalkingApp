"""Tests for Stripe payment helper functions."""
import pytest
from unittest.mock import patch, MagicMock
from core.stripe_integration import payment_intent_dashboard_url


def test_payment_intent_dashboard_url_test_mode():
    """Test that test mode PaymentIntents link to test dashboard."""
    with patch('core.stripe_key_manager.get_key_status') as mock_status:
        mock_status.return_value = {
            'configured': True,
            'mode': 'env',
            'test_or_live': 'test'
        }
        
        url = payment_intent_dashboard_url("pi_test_123456789")
        assert url == "https://dashboard.stripe.com/test/payments/pi_test_123456789"


def test_payment_intent_dashboard_url_live_mode():
    """Test that live mode PaymentIntents link to live dashboard."""
    with patch('core.stripe_key_manager.get_key_status') as mock_status:
        mock_status.return_value = {
            'configured': True,
            'mode': 'env',
            'test_or_live': 'live'
        }
        
        url = payment_intent_dashboard_url("pi_live_987654321")
        assert url == "https://dashboard.stripe.com/payments/pi_live_987654321"


def test_payment_intent_dashboard_url_defaults_to_test():
    """Test that missing mode defaults to test mode."""
    with patch('core.stripe_key_manager.get_key_status') as mock_status:
        mock_status.return_value = {
            'configured': True,
            'mode': None,
            'test_or_live': None
        }
        
        url = payment_intent_dashboard_url("pi_123456789")
        assert url == "https://dashboard.stripe.com/test/payments/pi_123456789"


@patch('core.stripe_integration.get_stripe_key')
@patch('core.stripe_integration.stripe.PaymentIntent')
def test_create_payment_intent_with_receipt_email(mock_pi, mock_key):
    """Test that create_payment_intent accepts receipt_email parameter."""
    from core.stripe_integration import create_payment_intent
    
    mock_key.return_value = "sk_test_fake_key_for_testing"
    mock_pi.create.return_value = MagicMock(client_secret="test_secret")
    
    result = create_payment_intent(
        amount_cents=5000,
        customer_id="cus_test123",
        metadata={"test": "data"},
        receipt_email="customer@example.com"
    )
    
    # Verify receipt_email was passed to Stripe
    mock_pi.create.assert_called_once()
    call_kwargs = mock_pi.create.call_args[1]
    assert call_kwargs['receipt_email'] == "customer@example.com"
    assert call_kwargs['amount'] == 5000
    assert call_kwargs['customer'] == "cus_test123"
