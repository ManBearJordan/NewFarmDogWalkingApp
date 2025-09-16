"""
Celery tasks for the dog walking application.

These tasks handle background processing for subscription syncing,
booking generation, and other maintenance operations.
"""

import logging
from celery import shared_task
from django.utils import timezone
from datetime import datetime, timedelta
from django.db import transaction
from .models import Subscription, Booking

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def sync_all_subscriptions(self, horizon_days=90):
    """
    Background task to sync all active subscriptions with Stripe.
    
    This task integrates with the existing subscription_sync.py module
    to perform the synchronization in the background.
    """
    try:
        # Import here to avoid circular imports
        from subscription_sync import sync_subscriptions_to_bookings_and_calendar
        
        logger.info("Starting background subscription sync")
        result = sync_subscriptions_to_bookings_and_calendar(horizon_days=horizon_days)
        
        # Update last sync time for all subscriptions
        Subscription.objects.filter(status='active').update(last_sync_at=timezone.now())
        
        logger.info(f"Subscription sync completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Subscription sync failed: {e}")
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def sync_single_subscription(self, stripe_subscription_id):
    """
    Background task to sync a single subscription with Stripe.
    """
    try:
        # Import here to avoid circular imports
        from subscription_sync import sync_on_subscription_change
        
        logger.info(f"Starting sync for subscription {stripe_subscription_id}")
        result = sync_on_subscription_change(stripe_subscription_id)
        
        # Update last sync time
        try:
            subscription = Subscription.objects.get(stripe_subscription_id=stripe_subscription_id)
            subscription.last_sync_at = timezone.now()
            subscription.save()
        except Subscription.DoesNotExist:
            logger.warning(f"Subscription {stripe_subscription_id} not found in Django models")
        
        logger.info(f"Subscription {stripe_subscription_id} sync completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Subscription {stripe_subscription_id} sync failed: {e}")
        raise


@shared_task(bind=True)
def generate_subscription_bookings(self, subscription_id, start_date=None, end_date=None):
    """
    Background task to generate bookings for a specific subscription.
    """
    try:
        subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
        
        # Import here to avoid circular imports
        from booking_utils import generate_bookings_and_update_calendar
        
        # Prepare schedule data from subscription
        schedule_data = {
            'service_code': subscription.service_code,
            'days': subscription.schedule_days,
            'start_time': subscription.schedule_start_time.strftime('%H:%M'),
            'end_time': subscription.schedule_end_time.strftime('%H:%M'),
            'location': subscription.schedule_location or '',
            'dogs': subscription.schedule_dogs,
            'notes': subscription.schedule_notes or ''
        }
        
        logger.info(f"Generating bookings for subscription {subscription_id}")
        result = generate_bookings_and_update_calendar(subscription_id, schedule_data)
        
        logger.info(f"Booking generation completed for {subscription_id}: {result}")
        return result
        
    except Subscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found")
        return {'success': False, 'error': 'Subscription not found'}
    except Exception as e:
        logger.error(f"Booking generation failed for {subscription_id}: {e}")
        raise


@shared_task(bind=True)
def cleanup_old_bookings(self, days_old=90):
    """
    Background task to clean up old completed or canceled bookings.
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        # Only clean up completed or canceled bookings
        old_bookings = Booking.objects.filter(
            status__in=['completed', 'canceled'],
            start_dt__lt=cutoff_date
        )
        
        count = old_bookings.count()
        
        # Keep bookings that have invoices
        old_bookings = old_bookings.filter(stripe_invoice_id__isnull=True)
        
        with transaction.atomic():
            deleted_count = old_bookings.delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old bookings (out of {count} candidates)")
        return {'cleaned_up': deleted_count, 'total_candidates': count}
        
    except Exception as e:
        logger.error(f"Booking cleanup failed: {e}")
        raise


@shared_task(bind=True)
def update_subscription_from_stripe(self, stripe_subscription_id):
    """
    Background task to update a single subscription from Stripe data.
    
    This is typically called in response to Stripe webhooks.
    """
    try:
        # Import here to avoid circular imports
        import stripe
        from django.conf import settings
        
        # Configure Stripe API key
        stripe.api_key = settings.STRIPE_LIVE_SECRET_KEY or settings.STRIPE_TEST_SECRET_KEY
        
        # Fetch subscription from Stripe
        stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
        
        # Extract schedule information
        from subscription_sync import extract_schedule_from_subscription, extract_service_code_from_metadata
        
        schedule_data = extract_schedule_from_subscription(stripe_sub)
        service_code = extract_service_code_from_metadata(stripe_sub)
        
        if not service_code:
            logger.warning(f"No valid service code found for subscription {stripe_subscription_id}")
            return {'success': False, 'error': 'No valid service code'}
        
        # Update or create Django model
        from core.models import Client
        
        # Get or create client
        stripe_customer = stripe.Customer.retrieve(stripe_sub.customer)
        client, created = Client.objects.get_or_create(
            stripe_customer_id=stripe_sub.customer,
            defaults={
                'name': stripe_customer.name or stripe_customer.email or 'Unknown',
                'email': stripe_customer.email,
            }
        )
        
        # Update or create subscription
        subscription, created = Subscription.objects.update_or_create(
            stripe_subscription_id=stripe_subscription_id,
            defaults={
                'client': client,
                'status': stripe_sub.status,
                'service_code': service_code,
                'service_name': service_code,  # This could be mapped from service_map
                'schedule_days': schedule_data.get('days', ''),
                'schedule_start_time': schedule_data.get('start_time', '09:00'),
                'schedule_end_time': schedule_data.get('end_time', '10:00'),
                'schedule_location': schedule_data.get('location', ''),
                'schedule_dogs': schedule_data.get('dogs', 1),
                'schedule_notes': schedule_data.get('notes', ''),
                'stripe_created_at': datetime.fromtimestamp(stripe_sub.created, tz=timezone.utc),
                'last_sync_at': timezone.now(),
            }
        )
        
        action = 'created' if created else 'updated'
        logger.info(f"Subscription {stripe_subscription_id} {action} successfully")
        
        # Trigger booking generation if subscription is active
        if stripe_sub.status == 'active':
            generate_subscription_bookings.delay(stripe_subscription_id)
        
        return {'success': True, 'action': action}
        
    except Exception as e:
        logger.error(f"Failed to update subscription {stripe_subscription_id}: {e}")
        raise


@shared_task(bind=True)
def process_stripe_webhook(self, event_type, event_data):
    """
    Background task to process Stripe webhook events.
    """
    try:
        logger.info(f"Processing Stripe webhook: {event_type}")
        
        if event_type in ['customer.subscription.created', 'customer.subscription.updated']:
            subscription_id = event_data['object']['id']
            update_subscription_from_stripe.delay(subscription_id)
            
        elif event_type == 'customer.subscription.deleted':
            subscription_id = event_data['object']['id']
            try:
                subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
                subscription.status = 'canceled'
                subscription.save()
                logger.info(f"Marked subscription {subscription_id} as canceled")
            except Subscription.DoesNotExist:
                logger.warning(f"Subscription {subscription_id} not found for deletion webhook")
        
        elif event_type in ['invoice.payment_succeeded', 'invoice.payment_failed']:
            # Handle invoice events if needed
            pass
        
        logger.info(f"Webhook {event_type} processed successfully")
        return {'success': True, 'event_type': event_type}
        
    except Exception as e:
        logger.error(f"Webhook processing failed for {event_type}: {e}")
        raise