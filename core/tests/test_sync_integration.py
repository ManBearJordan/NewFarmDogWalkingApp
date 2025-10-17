"""Integration tests for core.sync module."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from core.sync import (
    sync_customers,
    build_bookings_from_subscriptions,
    build_bookings_from_invoices,
    sync_all,
)
from core.models import Client, Booking


@pytest.mark.django_db
def test_sync_customers_creates_new_clients():
    """Test that sync_customers creates new clients from Stripe data"""
    # Mock Stripe customer data
    stripe_customers = [
        {
            "id": "cus_test123",
            "email": "test@example.com",
            "name": "Test Customer",
            "phone": "+1234567890",
            "address": {
                "line1": "123 Main St",
                "city": "San Francisco",
                "state": "CA",
                "postal_code": "94102",
            }
        },
        {
            "id": "cus_test456",
            "email": "another@example.com",
            "name": "Another Customer",
            "phone": None,
            "address": None,
        }
    ]
    
    with patch('core.sync.stripe') as mock_stripe:
        # Mock Customer.list to return our test data
        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = iter(stripe_customers)
        mock_stripe.Customer.list.return_value = mock_list
        
        with patch.dict('os.environ', {'STRIPE_API_KEY': 'sk_test_fake'}):
            result = sync_customers()
            
            assert result["processed"] == 2
            assert result["created"] == 2
            assert result["updated"] == 0
            
            # Verify clients were created
            client1 = Client.objects.get(stripe_customer_id="cus_test123")
            assert client1.email == "test@example.com"
            assert client1.name == "Test Customer"
            assert client1.phone == "+1234567890"
            assert "123 Main St" in client1.address
            
            client2 = Client.objects.get(stripe_customer_id="cus_test456")
            assert client2.email == "another@example.com"
            assert client2.name == "Another Customer"


@pytest.mark.django_db
def test_sync_customers_updates_existing_clients():
    """Test that sync_customers updates existing clients"""
    # Create an existing client
    existing = Client.objects.create(
        name="Old Name",
        email="test@example.com",
        phone="",
        address="",
        status="active",
        stripe_customer_id="cus_test123"
    )
    
    stripe_customers = [
        {
            "id": "cus_test123",
            "email": "test@example.com",
            "name": "Updated Name",
            "phone": "+1234567890",
            "address": {
                "line1": "456 New St",
                "city": "New York",
                "state": "NY",
                "postal_code": "10001",
            }
        }
    ]
    
    with patch('core.sync.stripe') as mock_stripe:
        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = iter(stripe_customers)
        mock_stripe.Customer.list.return_value = mock_list
        
        with patch.dict('os.environ', {'STRIPE_API_KEY': 'sk_test_fake'}):
            result = sync_customers()
            
            assert result["processed"] == 1
            assert result["created"] == 0
            assert result["updated"] == 1
            
            # Verify client was updated
            existing.refresh_from_db()
            assert existing.name == "Updated Name"
            assert existing.phone == "+1234567890"
            assert "456 New St" in existing.address


@pytest.mark.django_db
def test_build_bookings_from_subscriptions_creates_bookings():
    """Test that subscriptions create bookings"""
    # Create a client first
    client = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="",
        address="",
        status="active",
        stripe_customer_id="cus_test123"
    )
    
    # Mock Stripe subscription data
    now_ts = int(datetime.now(timezone.utc).timestamp())
    subscriptions = [
        {
            "id": "sub_test123",
            "customer": "cus_test123",
            "status": "active",
            "current_period_start": now_ts,
            "current_period_end": now_ts + 86400 * 30,  # 30 days later
        }
    ]
    
    with patch('core.sync.stripe') as mock_stripe:
        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = iter(subscriptions)
        mock_stripe.Subscription.list.return_value = mock_list
        
        with patch.dict('os.environ', {'STRIPE_API_KEY': 'sk_test_fake'}):
            result = build_bookings_from_subscriptions()
            
            assert result["processed"] == 1
            # Note: created/updated count depends on whether external_key field exists
            assert result["created"] + result["updated"] == 1
            
            # Verify booking was created
            bookings = Booking.objects.filter(client=client)
            assert bookings.count() == 1
            booking = bookings.first()
            assert booking.client == client


@pytest.mark.django_db
def test_build_bookings_from_invoices_creates_bookings():
    """Test that paid invoices create bookings"""
    # Create a client first
    client = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="",
        address="",
        status="active",
        stripe_customer_id="cus_test123"
    )
    
    # Mock Stripe invoice data
    now_ts = int(datetime.now(timezone.utc).timestamp())
    invoices = [
        {
            "id": "in_test123",
            "customer": "cus_test123",
            "status": "paid",
            "created": now_ts,
        }
    ]
    
    with patch('core.sync.stripe') as mock_stripe:
        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = iter(invoices)
        mock_stripe.Invoice.list.return_value = mock_list
        
        with patch.dict('os.environ', {'STRIPE_API_KEY': 'sk_test_fake'}):
            result = build_bookings_from_invoices()
            
            assert result["processed"] == 1
            assert result["created"] + result["updated"] == 1
            
            # Verify booking was created
            bookings = Booking.objects.filter(client=client)
            assert bookings.count() == 1
            booking = bookings.first()
            assert booking.client == client


@pytest.mark.django_db
def test_build_bookings_creates_client_if_missing():
    """Test that bookings create missing clients"""
    # No pre-existing client
    
    # Mock Stripe subscription data
    now_ts = int(datetime.now(timezone.utc).timestamp())
    subscriptions = [
        {
            "id": "sub_test123",
            "customer": "cus_test123",
            "status": "active",
            "current_period_start": now_ts,
            "current_period_end": now_ts + 86400 * 30,
        }
    ]
    
    stripe_customer = {
        "id": "cus_test123",
        "email": "test@example.com",
        "name": "Test Customer",
        "phone": None,
        "address": None,
    }
    
    with patch('core.sync.stripe') as mock_stripe:
        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = iter(subscriptions)
        mock_stripe.Subscription.list.return_value = mock_list
        # Mock Customer.retrieve for when client is not found
        mock_stripe.Customer.retrieve.return_value = stripe_customer
        
        with patch.dict('os.environ', {'STRIPE_API_KEY': 'sk_test_fake'}):
            result = build_bookings_from_subscriptions()
            
            assert result["processed"] == 1
            
            # Verify client was created
            client = Client.objects.get(stripe_customer_id="cus_test123")
            assert client.email == "test@example.com"
            
            # Verify booking was created with the new client
            bookings = Booking.objects.filter(client=client)
            assert bookings.count() == 1


@pytest.mark.django_db
def test_sync_all_runs_all_syncs():
    """Test that sync_all runs all sync functions"""
    with patch('core.sync.stripe') as mock_stripe:
        # Mock all Stripe list operations
        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = iter([])
        mock_stripe.Customer.list.return_value = mock_list
        mock_stripe.Invoice.list.return_value = mock_list
        mock_stripe.Subscription.list.return_value = mock_list
        
        with patch.dict('os.environ', {'STRIPE_API_KEY': 'sk_test_fake'}):
            result = sync_all()
            
            # Verify all three syncs ran
            assert "customers" in result
            assert "subs" in result
            assert "invoices" in result
            
            # All should have processed 0 items
            assert result["customers"]["processed"] == 0
            assert result["subs"]["processed"] == 0
            assert result["invoices"]["processed"] == 0


@pytest.mark.django_db
def test_sync_handles_missing_stripe_key():
    """Test that sync functions handle missing Stripe key gracefully"""
    with patch.dict('os.environ', {}, clear=True):
        with pytest.raises(RuntimeError) as exc_info:
            sync_customers()
        assert "STRIPE_API_KEY" in str(exc_info.value) or "STRIPE_SECRET_KEY" in str(exc_info.value)


@pytest.mark.django_db
def test_sync_skips_subscriptions_without_customer():
    """Test that subscriptions without customer IDs are skipped"""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    subscriptions = [
        {
            "id": "sub_test123",
            "customer": None,  # Missing customer
            "status": "active",
            "current_period_start": now_ts,
            "current_period_end": now_ts + 86400 * 30,
        }
    ]
    
    with patch('core.sync.stripe') as mock_stripe:
        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = iter(subscriptions)
        mock_stripe.Subscription.list.return_value = mock_list
        
        with patch.dict('os.environ', {'STRIPE_API_KEY': 'sk_test_fake'}):
            result = build_bookings_from_subscriptions()
            
            # Should process but not create any bookings
            assert result["processed"] == 1
            assert result["created"] == 0
            assert result["updated"] == 0
            assert Booking.objects.count() == 0


@pytest.mark.django_db
def test_sync_skips_invoices_without_customer():
    """Test that invoices without customer IDs are skipped"""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    invoices = [
        {
            "id": "in_test123",
            "customer": None,  # Missing customer
            "status": "paid",
            "created": now_ts,
        }
    ]
    
    with patch('core.sync.stripe') as mock_stripe:
        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = iter(invoices)
        mock_stripe.Invoice.list.return_value = mock_list
        
        with patch.dict('os.environ', {'STRIPE_API_KEY': 'sk_test_fake'}):
            result = build_bookings_from_invoices()
            
            # Should process but not create any bookings
            assert result["processed"] == 1
            assert result["created"] == 0
            assert result["updated"] == 0
            assert Booking.objects.count() == 0


@pytest.mark.django_db
def test_sync_customers_with_missing_email():
    """Test that sync_customers handles customers without email addresses"""
    stripe_customers = [
        {
            "id": "cus_no_email1",
            "email": None,  # No email
            "name": "Customer Without Email",
            "phone": "+1234567890",
            "address": None,
        },
        {
            "id": "cus_no_email2",
            "email": "",  # Empty email
            "name": "Another Customer",
            "phone": None,
            "address": None,
        },
        {
            "id": "cus_invalid_email",
            "email": "not-an-email",  # Invalid email format
            "name": "Customer With Invalid Email",
            "phone": None,
            "address": None,
        }
    ]
    
    with patch('core.sync.stripe') as mock_stripe:
        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = iter(stripe_customers)
        mock_stripe.Customer.list.return_value = mock_list
        
        with patch.dict('os.environ', {'STRIPE_API_KEY': 'sk_test_fake'}):
            result = sync_customers()
            
            # All customers should be processed and created with synthesized emails
            assert result["processed"] == 3
            assert result["created"] == 3
            assert result["updated"] == 0
            
            # Verify clients were created with synthesized emails
            client1 = Client.objects.get(stripe_customer_id="cus_no_email1")
            assert client1.email == "customer_cus_no_email1@stripe.local"
            assert client1.name == "Customer Without Email"
            
            client2 = Client.objects.get(stripe_customer_id="cus_no_email2")
            assert client2.email == "customer_cus_no_email2@stripe.local"
            assert client2.name == "Another Customer"
            
            client3 = Client.objects.get(stripe_customer_id="cus_invalid_email")
            assert client3.email == "customer_cus_invalid_email@stripe.local"
            assert client3.name == "Customer With Invalid Email"
