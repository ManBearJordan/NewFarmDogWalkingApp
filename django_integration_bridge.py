"""
Integration bridge between existing codebase and new Django models.

This module shows how to gradually integrate Django models with the existing
codebase without breaking any existing functionality.
"""

import os
import django
from typing import Optional, Dict, Any, List

# Set up Django (this is safe to call multiple times)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dogwalking_django.settings')
django.setup()

from core.models import Client as DjangoClient, Subscription as DjangoSubscription, Booking as DjangoBooking
from django.utils import timezone
from datetime import datetime, time


class DjangoBridge:
    """
    Bridge class to integrate Django models with existing code.
    
    This allows the existing codebase to optionally use Django models
    while maintaining full backward compatibility.
    """
    
    @staticmethod
    def sync_client_to_django(client_data: Dict[str, Any]) -> Optional[DjangoClient]:
        """
        Sync a client from the existing system to Django models.
        
        Args:
            client_data: Dictionary with client information
            
        Returns:
            Django Client instance or None
        """
        try:
            client, created = DjangoClient.objects.update_or_create(
                stripe_customer_id=client_data.get('stripe_customer_id'),
                defaults={
                    'name': client_data.get('name', 'Unknown'),
                    'email': client_data.get('email'),
                    'phone': client_data.get('phone'),
                    'address': client_data.get('address'),
                    'credit_cents': client_data.get('credit_cents', 0),
                    'status': client_data.get('status', 'active'),
                }
            )
            return client
        except Exception as e:
            print(f"Warning: Could not sync client to Django: {e}")
            return None
    
    @staticmethod
    def sync_subscription_to_django(subscription_data: Dict[str, Any]) -> Optional[DjangoSubscription]:
        """
        Sync a subscription from Stripe to Django models.
        
        Args:
            subscription_data: Dictionary with subscription information
            
        Returns:
            Django Subscription instance or None
        """
        try:
            # Get or create client first
            stripe_customer_id = subscription_data.get('customer_id')
            if not stripe_customer_id:
                return None
            
            client = DjangoClient.objects.filter(stripe_customer_id=stripe_customer_id).first()
            if not client:
                # Create minimal client record
                client = DjangoClient.objects.create(
                    stripe_customer_id=stripe_customer_id,
                    name=f"Customer {stripe_customer_id}"
                )
            
            # Parse schedule data
            schedule = subscription_data.get('schedule', {})
            
            subscription, created = DjangoSubscription.objects.update_or_create(
                stripe_subscription_id=subscription_data['stripe_subscription_id'],
                defaults={
                    'client': client,
                    'status': subscription_data.get('status', 'active'),
                    'service_code': subscription_data.get('service_code', 'DOG_WALK'),
                    'service_name': subscription_data.get('service_name', 'Dog Walking'),
                    'schedule_days': schedule.get('days', ''),
                    'schedule_start_time': schedule.get('start_time', '09:00'),
                    'schedule_end_time': schedule.get('end_time', '10:00'),
                    'schedule_location': schedule.get('location', ''),
                    'schedule_dogs': schedule.get('dogs', 1),
                    'schedule_notes': schedule.get('notes', ''),
                    'last_sync_at': timezone.now(),
                }
            )
            return subscription
        except Exception as e:
            print(f"Warning: Could not sync subscription to Django: {e}")
            return None
    
    @staticmethod
    def sync_booking_to_django(booking_data: Dict[str, Any]) -> Optional[DjangoBooking]:
        """
        Sync a booking to Django models.
        
        Args:
            booking_data: Dictionary with booking information
            
        Returns:
            Django Booking instance or None
        """
        try:
            # Get client
            client = None
            if 'client_id' in booking_data:
                client = DjangoClient.objects.filter(id=booking_data['client_id']).first()
            elif 'stripe_customer_id' in booking_data:
                client = DjangoClient.objects.filter(
                    stripe_customer_id=booking_data['stripe_customer_id']
                ).first()
            
            if not client:
                return None
            
            # Get subscription if available
            subscription = None
            if booking_data.get('created_from_sub_id'):
                subscription = DjangoSubscription.objects.filter(
                    stripe_subscription_id=booking_data['created_from_sub_id']
                ).first()
            
            booking, created = DjangoBooking.objects.update_or_create(
                id=booking_data.get('id'),
                defaults={
                    'client': client,
                    'subscription': subscription,
                    'start_dt': booking_data['start_dt'],
                    'end_dt': booking_data['end_dt'],
                    'service_type': booking_data.get('service_type', 'DOG_WALK'),
                    'service_name': booking_data.get('service_name', 'Dog Walking'),
                    'location': booking_data.get('location', ''),
                    'dogs': booking_data.get('dogs', 1),
                    'notes': booking_data.get('notes', ''),
                    'status': booking_data.get('status', 'scheduled'),
                    'source': booking_data.get('source', 'manual'),
                    'created_from_sub_id': booking_data.get('created_from_sub_id'),
                    'stripe_invoice_id': booking_data.get('stripe_invoice_id'),
                    'stripe_price_id': booking_data.get('stripe_price_id'),
                    'invoice_url': booking_data.get('invoice_url'),
                }
            )
            return booking
        except Exception as e:
            print(f"Warning: Could not sync booking to Django: {e}")
            return None


def enhanced_subscription_sync(conn, subscription_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced version of subscription sync that also updates Django models.
    
    This function wraps the existing subscription sync functionality and
    optionally syncs data to Django models for enhanced management.
    """
    # Import existing sync function
    try:
        from subscription_sync import sync_subscription_to_bookings
        
        # Run existing sync logic
        result = sync_subscription_to_bookings(conn, subscription_data)
        
        # Additionally sync to Django (non-blocking)
        try:
            django_subscription = DjangoBridge.sync_subscription_to_django(subscription_data)
            if django_subscription:
                result['django_synced'] = True
                result['django_subscription_id'] = django_subscription.id
        except Exception as e:
            print(f"Note: Django sync not available: {e}")
            result['django_synced'] = False
        
        return result
        
    except ImportError:
        print("Original subscription_sync module not available")
        return {'error': 'Original module not found'}


def enhanced_booking_creation(conn, booking_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced booking creation that also creates Django model.
    """
    try:
        # Import existing booking function
        from db import add_booking
        
        # Create booking using existing method
        booking_id = add_booking(
            conn, 
            booking_data['client_id'],
            booking_data['start_dt'],
            booking_data['end_dt'],
            booking_data.get('service_type', 'DOG_WALK'),
            booking_data.get('location', ''),
            booking_data.get('notes', '')
        )
        
        # Additionally sync to Django
        booking_data['id'] = booking_id
        django_booking = DjangoBridge.sync_booking_to_django(booking_data)
        
        return {
            'booking_id': booking_id,
            'django_synced': django_booking is not None,
            'django_booking_id': django_booking.id if django_booking else None
        }
        
    except ImportError:
        print("Original db module not available")
        return {'error': 'Original module not found'}


def example_usage():
    """
    Example showing how existing code can be enhanced with Django models.
    """
    print("=== Django Integration Bridge Example ===\n")
    
    # Example 1: Existing subscription sync with Django enhancement
    print("1. Enhanced subscription sync:")
    
    sample_subscription = {
        'stripe_subscription_id': 'sub_example123',
        'customer_id': 'cus_example123',
        'status': 'active',
        'service_code': 'WALK_SHORT_SINGLE',
        'service_name': 'Short Dog Walk',
        'schedule': {
            'days': 'MON,WED,FRI',
            'start_time': '09:00',
            'end_time': '10:00',
            'location': 'Central Park',
            'dogs': 2,
            'notes': 'Bring treats'
        }
    }
    
    # This would use the existing database connection
    # result = enhanced_subscription_sync(conn, sample_subscription)
    # print(f"Sync result: {result}")
    
    # For demo, just sync to Django
    django_sub = DjangoBridge.sync_subscription_to_django(sample_subscription)
    if django_sub:
        print(f"✓ Synced to Django: {django_sub}")
    
    # Example 2: Enhanced booking creation
    print("\n2. Enhanced booking creation:")
    
    sample_booking = {
        'client_id': 1,
        'stripe_customer_id': 'cus_example123',
        'start_dt': timezone.now(),
        'end_dt': timezone.now(),
        'service_type': 'WALK_SHORT_SINGLE',
        'service_name': 'Short Dog Walk',
        'location': 'Central Park',
        'dogs': 2,
        'notes': 'Regular walk',
        'created_from_sub_id': 'sub_example123'
    }
    
    django_booking = DjangoBridge.sync_booking_to_django(sample_booking)
    if django_booking:
        print(f"✓ Synced to Django: {django_booking}")
    
    print("\n3. Benefits of Django integration:")
    print("- Web-based admin interface")
    print("- REST API for external integrations")
    print("- Background task processing")
    print("- Enhanced reporting and analytics")
    print("- Mobile app development support")
    
    print("\n4. Database state:")
    print(f"- Django Clients: {DjangoClient.objects.count()}")
    print(f"- Django Subscriptions: {DjangoSubscription.objects.count()}")
    print(f"- Django Bookings: {DjangoBooking.objects.count()}")


if __name__ == "__main__":
    example_usage()