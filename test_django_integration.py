"""
Test Django integration for the dog walking application.

This test verifies that the Django models work correctly and can
integrate with the existing codebase.
"""

import os
import django
from datetime import time, datetime
from django.utils import timezone

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dogwalking_django.settings')
django.setup()

from core.models import Client, Subscription, Booking, Schedule


def test_client_creation():
    """Test creating a client"""
    print("Testing client creation...")
    
    client = Client.objects.create(
        name="Test Client",
        email="test@example.com",
        phone="555-0123",
        stripe_customer_id="cus_test123",
        credit_cents=5000
    )
    
    assert client.name == "Test Client"
    assert client.credit_dollars == 50.0
    print(f"✓ Client created: {client}")
    return client


def test_subscription_creation():
    """Test creating a subscription"""
    print("Testing subscription creation...")
    
    client = Client.objects.first()
    if not client:
        client = test_client_creation()
    
    subscription = Subscription.objects.create(
        stripe_subscription_id="sub_test123",
        client=client,
        service_code="WALK_SHORT_SINGLE",
        service_name="Short Dog Walk",
        schedule_days="MON,WED,FRI",
        schedule_start_time=time(9, 0),
        schedule_end_time=time(10, 0),
        schedule_location="Test Park",
        schedule_dogs=2,
        schedule_notes="Test subscription"
    )
    
    assert subscription.client == client
    assert len(subscription.schedule_days_list) == 3
    assert subscription.schedule_duration.total_seconds() == 3600  # 1 hour
    print(f"✓ Subscription created: {subscription}")
    return subscription


def test_booking_creation():
    """Test creating a booking"""
    print("Testing booking creation...")
    
    client = Client.objects.first()
    subscription = Subscription.objects.first()
    
    if not client:
        client = test_client_creation()
    if not subscription:
        subscription = test_subscription_creation()
    
    booking = Booking.objects.create(
        client=client,
        subscription=subscription,
        start_dt=timezone.now(),
        end_dt=timezone.now(),
        service_type="WALK_SHORT_SINGLE",
        service_name="Short Dog Walk",
        location="Test Park",
        dogs=2,
        notes="Test booking",
        created_from_sub_id=subscription.stripe_subscription_id
    )
    
    assert booking.client == client
    assert booking.subscription == subscription
    assert booking.is_today
    print(f"✓ Booking created: {booking}")
    return booking


def test_schedule_template():
    """Test creating a schedule template"""
    print("Testing schedule template...")
    
    schedule = Schedule.objects.create(
        name="Standard Walk Schedule",
        description="Monday, Wednesday, Friday morning walks",
        days_of_week="[0, 2, 4]",  # Mon, Wed, Fri
        start_time=time(9, 0),
        end_time=time(10, 0),
        service_code="WALK_SHORT_SINGLE",
        default_location="Local Park",
        default_dogs=1
    )
    
    assert schedule.name == "Standard Walk Schedule"
    assert len(schedule.days_list) == 3
    print(f"✓ Schedule template created: {schedule}")
    return schedule


def test_model_relationships():
    """Test model relationships"""
    print("Testing model relationships...")
    
    client = Client.objects.first()
    if not client:
        client = test_client_creation()
        test_subscription_creation()
        test_booking_creation()
    
    # Test client relationships
    subscriptions = client.subscriptions.all()
    bookings = client.bookings.all()
    
    print(f"✓ Client has {subscriptions.count()} subscriptions")
    print(f"✓ Client has {bookings.count()} bookings")
    
    # Test subscription relationships
    if subscriptions.exists():
        subscription = subscriptions.first()
        sub_bookings = subscription.bookings.all()
        print(f"✓ Subscription has {sub_bookings.count()} bookings")
        
        next_occurrence = subscription.get_next_occurrence()
        print(f"✓ Next occurrence: {next_occurrence}")


def test_admin_integration():
    """Test that admin interface would work"""
    print("Testing admin integration...")
    
    # Test model string representations
    client = Client.objects.first()
    subscription = Subscription.objects.first()
    booking = Booking.objects.first()
    schedule = Schedule.objects.first()
    
    if client:
        print(f"✓ Client str: {str(client)}")
    if subscription:
        print(f"✓ Subscription str: {str(subscription)}")
    if booking:
        print(f"✓ Booking str: {str(booking)}")
    if schedule:
        print(f"✓ Schedule str: {str(schedule)}")


def run_all_tests():
    """Run all Django integration tests"""
    print("=== Django Integration Tests ===\n")
    
    try:
        # Create test data
        client = test_client_creation()
        subscription = test_subscription_creation()
        booking = test_booking_creation()
        schedule = test_schedule_template()
        
        # Test relationships
        test_model_relationships()
        
        # Test admin interface compatibility
        test_admin_integration()
        
        print("\n=== All Tests Passed! ===")
        print("Django models are working correctly and ready for use.")
        
        # Display summary
        print(f"\nDatabase Summary:")
        print(f"- Clients: {Client.objects.count()}")
        print(f"- Subscriptions: {Subscription.objects.count()}")
        print(f"- Bookings: {Booking.objects.count()}")
        print(f"- Schedule Templates: {Schedule.objects.count()}")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    run_all_tests()