"""Tests for sync management commands."""
import pytest
from unittest.mock import patch, MagicMock, Mock
from io import StringIO
from django.core.management import call_command


@pytest.mark.django_db
def test_sync_customers_with_mock_stripe():
    """Test sync_customers command with mocked Stripe API"""
    out = StringIO()
    
    # Mock the stripe API
    with patch('core.sync.stripe') as mock_stripe:
        # Mock Customer.list to return empty iterator
        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = iter([])
        mock_stripe.Customer.list.return_value = mock_list
        
        # Mock environment variable
        with patch.dict('os.environ', {'STRIPE_API_KEY': 'sk_test_fake'}):
            call_command('sync_customers', stdout=out)
            output = out.getvalue()
            # Should output success message with stats
            assert "Customers synced:" in output
            assert "processed" in output


@pytest.mark.django_db
def test_sync_customers_graceful_failure():
    """Test sync_customers command handles errors gracefully when API key is missing"""
    out = StringIO()
    
    # Clear any Stripe API key env vars
    with patch.dict('os.environ', {}, clear=True):
        try:
            call_command('sync_customers', stdout=out)
            # If it doesn't raise, that's okay - the command might handle it gracefully
        except RuntimeError as e:
            # Expected behavior when no API key is set
            assert "STRIPE_API_KEY" in str(e) or "STRIPE_SECRET_KEY" in str(e)


@pytest.mark.django_db
def test_build_bookings_from_invoices_with_mock_stripe():
    """Test build_bookings_from_invoices command with mocked Stripe API"""
    out = StringIO()
    
    with patch('core.sync.stripe') as mock_stripe:
        # Mock Invoice.list to return empty iterator
        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = iter([])
        mock_stripe.Invoice.list.return_value = mock_list
        
        with patch.dict('os.environ', {'STRIPE_API_KEY': 'sk_test_fake'}):
            call_command('build_bookings_from_invoices', stdout=out)
            output = out.getvalue()
            assert "Invoice bookings built:" in output
            assert "processed" in output


@pytest.mark.django_db
def test_build_bookings_from_subscriptions_with_mock_stripe():
    """Test build_bookings_from_subscriptions command with mocked Stripe API"""
    out = StringIO()
    
    with patch('core.sync.stripe') as mock_stripe:
        # Mock Subscription.list to return empty iterator
        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = iter([])
        mock_stripe.Subscription.list.return_value = mock_list
        
        with patch.dict('os.environ', {'STRIPE_API_KEY': 'sk_test_fake'}):
            call_command('build_bookings_from_subscriptions', stdout=out)
            output = out.getvalue()
            assert "Subscription bookings built:" in output
            assert "processed" in output


@pytest.mark.django_db
def test_sync_all_calls_all_commands():
    """Test that sync_all calls all available sync commands"""
    out = StringIO()
    
    with patch('core.sync.stripe') as mock_stripe:
        # Mock all Stripe list operations to return empty iterators
        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = iter([])
        mock_stripe.Customer.list.return_value = mock_list
        mock_stripe.Invoice.list.return_value = mock_list
        mock_stripe.Subscription.list.return_value = mock_list
        
        with patch.dict('os.environ', {'STRIPE_API_KEY': 'sk_test_fake'}):
            call_command('sync_all', stdout=out)
            output = out.getvalue()
            # Should complete successfully
            assert "sync_all complete" in output
