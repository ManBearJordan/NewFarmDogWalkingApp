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
    return generate_subscription_bookings_sync(subscription_id, start_date, end_date)


def generate_subscription_bookings_sync(subscription_id, start_date=None, end_date=None):
    """
    Synchronous version of booking generation for immediate processing.
    Used by webhooks and other automated triggers that need immediate results.
    """
    try:
        from log_utils import log_subscription_info, log_subscription_error
        
        subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
        
        # Import here to avoid circular imports
        from subscription_sync import sync_subscriptions_to_bookings_and_calendar
        
        # Prepare schedule data from subscription
        schedule_data = {
            'service_code': subscription.service_code,
            'days': subscription.schedule_days,
            'start_time': subscription.schedule_start_time.strftime('%H:%M') if subscription.schedule_start_time else '09:00',
            'end_time': subscription.schedule_end_time.strftime('%H:%M') if subscription.schedule_end_time else '10:00',
            'location': subscription.schedule_location or '',
            'dogs': subscription.schedule_dogs,
            'notes': subscription.schedule_notes or ''
        }
        
        logger.info(f"Generating bookings for subscription {subscription_id} with schedule: {schedule_data}")
        log_subscription_info(f"Starting booking generation for subscription {subscription_id}", subscription_id)
        
        # Call the main sync function which handles booking generation
        result = sync_subscriptions_to_bookings_and_calendar(None, horizon_days=90)
        
        if result.get('bookings_created', 0) > 0:
            log_subscription_info(f"Booking generation SUCCESS: {result['bookings_created']} bookings created", subscription_id)
        else:
            log_subscription_info(f"Booking generation completed: No new bookings needed", subscription_id)
        
        logger.info(f"Booking generation completed for {subscription_id}: {result}")
        return {
            'success': True,
            'bookings_created': result.get('bookings_created', 0),
            'result': result
        }
        
    except Subscription.DoesNotExist:
        error_msg = f"Subscription {subscription_id} not found"
        logger.error(error_msg)
        log_subscription_error(error_msg, subscription_id)
        return {'success': False, 'error': 'Subscription not found'}
    except Exception as e:
        error_msg = f"Booking generation failed for {subscription_id}: {e}"
        logger.error(error_msg)
        log_subscription_error(error_msg, subscription_id, e)
        return {'success': False, 'error': str(e)}


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
    AUTOMATICALLY GENERATES BOOKINGS if subscription has valid schedule metadata.
    ENHANCED: Comprehensive step-by-step logging per problem statement.
    """
    try:
        # Import here to avoid circular imports
        import stripe
        from django.conf import settings
        from log_utils import log_subscription_info, log_subscription_error
        
        # WEBHOOK STEP 1: Configure and retrieve subscription
        log_subscription_info(f"WEBHOOK STEP 1: Starting webhook processing", stripe_subscription_id)
        
        # Configure Stripe API key
        stripe.api_key = settings.STRIPE_LIVE_SECRET_KEY or settings.STRIPE_TEST_SECRET_KEY
        
        logger.info(f"Webhook triggered: Processing subscription {stripe_subscription_id}")
        log_subscription_info(f"WEBHOOK STEP 1: Fetching subscription from Stripe", stripe_subscription_id)
        
        # Fetch subscription from Stripe
        stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
        log_subscription_info(f"WEBHOOK STEP 1 SUCCESS: Retrieved subscription data", stripe_subscription_id)
        
        # WEBHOOK STEP 2: Extract and validate metadata
        log_subscription_info(f"WEBHOOK STEP 2: Extracting schedule and service metadata", stripe_subscription_id)
        from subscription_sync import extract_schedule_from_subscription, extract_service_code_from_metadata
        
        schedule_data = extract_schedule_from_subscription(stripe_sub)
        service_code = extract_service_code_from_metadata(stripe_sub)
        
        if not service_code:
            error_msg = f"WEBHOOK STEP 2 FAILED: No valid service code found"
            logger.warning(error_msg)
            log_subscription_error(error_msg, stripe_subscription_id)
            return {'success': False, 'error': 'No valid service code'}
        
        log_subscription_info(f"WEBHOOK STEP 2: Found service_code='{service_code}'", stripe_subscription_id)
        
        # Validate schedule metadata
        if not schedule_data.get('days') or not schedule_data.get('start_time') or not schedule_data.get('end_time'):
            error_msg = f"WEBHOOK STEP 2 FAILED: Missing required schedule metadata - days={schedule_data.get('days')}, start_time={schedule_data.get('start_time')}, end_time={schedule_data.get('end_time')}"
            logger.warning(error_msg)
            log_subscription_error(error_msg, stripe_subscription_id)
            return {'success': False, 'error': 'Missing schedule metadata', 'schedule_data': schedule_data}
        
        log_subscription_info(f"WEBHOOK STEP 2 SUCCESS: Valid schedule metadata found", stripe_subscription_id)
        
        # WEBHOOK STEP 3: Client lookup/creation
        log_subscription_info(f"WEBHOOK STEP 3: Processing client data", stripe_subscription_id)
        from core.models import Client
        
        # Get or create client
        try:
            stripe_customer = stripe.Customer.retrieve(stripe_sub.customer)
            log_subscription_info(f"WEBHOOK STEP 3: Retrieved Stripe customer data", stripe_subscription_id)
            
            client, client_created = Client.objects.get_or_create(
                stripe_customer_id=stripe_sub.customer,
                defaults={
                    'name': stripe_customer.name or stripe_customer.email or 'Unknown',
                    'email': stripe_customer.email,
                }
            )
            if client_created:
                log_subscription_info(f"WEBHOOK STEP 3: New client created - {client.name}", stripe_subscription_id)
            else:
                log_subscription_info(f"WEBHOOK STEP 3: Existing client found - {client.name}", stripe_subscription_id)
            log_subscription_info(f"WEBHOOK STEP 3 SUCCESS: Client processed - ID={client.id}", stripe_subscription_id)
            
        except Exception as client_error:
            error_msg = f"WEBHOOK STEP 3 FAILED: Error processing client: {client_error}"
            logger.error(error_msg)
            log_subscription_error(error_msg, stripe_subscription_id, client_error)
            return {'success': False, 'error': 'Client lookup/creation failed'}
        
        # WEBHOOK STEP 4: Create/update subscription in database
        log_subscription_info(f"WEBHOOK STEP 4: Creating/updating subscription in database", stripe_subscription_id)
        
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
        log_subscription_info(f"WEBHOOK STEP 4 SUCCESS: Subscription {action} - Service: {service_code}, Schedule: {schedule_data.get('days')} {schedule_data.get('start_time')}-{schedule_data.get('end_time')}", stripe_subscription_id)
        
        # WEBHOOK STEP 5: AUTOMATICALLY trigger booking generation if subscription is active AND has valid schedule
        if stripe_sub.status == 'active':
            try:
                log_subscription_info(f"WEBHOOK STEP 5: AUTO-GENERATING bookings for active subscription", stripe_subscription_id)
                logger.info(f"AUTO-GENERATING bookings for active subscription {stripe_subscription_id}")
                
                # Call booking generation immediately (synchronous for webhook reliability)
                booking_result = generate_subscription_bookings_sync(stripe_subscription_id)
                
                if booking_result.get('success'):
                    log_subscription_info(f"WEBHOOK STEP 5 SUCCESS: Auto-booking completed - {booking_result.get('bookings_created', 0)} bookings created", stripe_subscription_id)
                else:
                    log_subscription_error(f"WEBHOOK STEP 5 FAILED: Auto-booking failed - {booking_result.get('error', 'Unknown error')}", stripe_subscription_id)
                    
                return {
                    'success': True, 
                    'action': action,
                    'booking_generation': booking_result
                }
            except Exception as booking_error:
                error_msg = f"WEBHOOK STEP 5 FAILED: Booking generation failed after subscription update: {booking_error}"
                logger.error(error_msg)
                log_subscription_error(error_msg, stripe_subscription_id, booking_error)
                # Still return success for subscription update, but note booking failure
                return {
                    'success': True, 
                    'action': action,
                    'booking_generation': {'success': False, 'error': str(booking_error)}
                }
        else:
            log_subscription_info(f"Subscription {stripe_subscription_id} is not active ({stripe_sub.status}), skipping booking generation", stripe_subscription_id)
        
        return {'success': True, 'action': action}
        
    except Exception as e:
        error_msg = f"Failed to update subscription {stripe_subscription_id}: {e}"
        logger.error(error_msg)
        log_subscription_error(error_msg, stripe_subscription_id, e)
        raise


@shared_task(bind=True)
def process_stripe_webhook(self, event_type, event_data):
    """
    Background task to process Stripe webhook events.
    AUTOMATICALLY TRIGGERS booking generation for subscription events.
    """
    try:
        from log_utils import log_subscription_info, log_subscription_error
        
        logger.info(f"Processing Stripe webhook: {event_type}")
        log_subscription_info(f"Webhook received: {event_type}")
        
        if event_type in ['customer.subscription.created', 'customer.subscription.updated']:
            subscription_id = event_data['object']['id']
            
            logger.info(f"Webhook: Processing subscription {event_type} for {subscription_id}")
            log_subscription_info(f"Webhook processing: {event_type} for subscription {subscription_id}", subscription_id)
            
            # This will automatically generate bookings if the subscription is active
            update_subscription_from_stripe.delay(subscription_id)
            
        elif event_type == 'customer.subscription.deleted':
            subscription_id = event_data['object']['id']
            
            try:
                subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
                subscription.status = 'canceled'
                subscription.save()
                
                logger.info(f"Marked subscription {subscription_id} as canceled")
                log_subscription_info(f"Subscription marked as canceled due to webhook", subscription_id)
                
                # TODO: Should we also cleanup/cancel future bookings here?
                
            except Subscription.DoesNotExist:
                error_msg = f"Subscription {subscription_id} not found for deletion webhook"
                logger.warning(error_msg)
                log_subscription_error(error_msg, subscription_id)
        
        elif event_type in ['invoice.payment_succeeded', 'invoice.payment_failed']:
            # Handle invoice events if needed
            invoice_id = event_data['object']['id']
            logger.info(f"Invoice event {event_type} for {invoice_id} - no action taken currently")
        
        else:
            logger.info(f"Webhook event {event_type} - no handler configured")
        
        logger.info(f"Webhook {event_type} processed successfully")
        log_subscription_info(f"Webhook processing completed: {event_type}")
        
        return {'success': True, 'event_type': event_type}
        
    except Exception as e:
        error_msg = f"Webhook processing failed for {event_type}: {e}"
        logger.error(error_msg)
        log_subscription_error(error_msg, event_type, e)
        raise