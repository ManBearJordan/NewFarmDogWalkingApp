"""
Django-integrated Stripe sync service.

This module provides the Django-integrated Stripe sync system that:
1. Fetches active subscriptions and invoices using djstripe
2. Links subscriptions and invoices to Bookings and Calendar entries
3. Ensures Bookings and Calendar reflect current active subscriptions/invoices
4. Provides detailed error logging and admin panel integration
5. Runs automatically on Django app startup via core/apps.py ready() method
"""

import logging
import sqlite3
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction, connection
from django.core.exceptions import ObjectDoesNotExist

# Import djstripe models for Stripe data access
from djstripe.models import Subscription as DjstripeSubscription, Invoice as DjstripeInvoice, Customer as DjstripeCustomer

# Import our Django models
from core.models import Subscription, Booking, Client

# Import existing sync functionality
try:
    from subscription_sync import sync_subscriptions_to_bookings_and_calendar
    from stripe_integration import list_active_subscriptions, _api
    LEGACY_SYNC_AVAILABLE = True
except ImportError:
    LEGACY_SYNC_AVAILABLE = False

logger = logging.getLogger(__name__)


class StripeSyncService:
    """
    Django-integrated service for syncing Stripe subscriptions and invoices.
    
    This service bridges the existing PySide6-based sync system with Django ORM
    and provides structured sync functionality with proper error handling.
    """

    def __init__(self):
        self.sync_stats = {
            'subscriptions_processed': 0,
            'subscriptions_created': 0,
            'subscriptions_updated': 0,
            'bookings_created': 0,
            'bookings_updated': 0,
            'invoices_linked': 0,
            'clients_created': 0,
            'clients_updated': 0,
            'errors': []
        }

    def sync_all_stripe_data(self, horizon_days: int = 90) -> Dict[str, Any]:
        """
        Sync all active Stripe subscriptions and invoices to Django models.
        
        Args:
            horizon_days: Number of days ahead to generate bookings
            
        Returns:
            Dictionary with sync results and statistics
        """
        logger.info("Starting Django-integrated Stripe sync")
        
        try:
            with transaction.atomic():
                # Step 1: Sync subscriptions using djstripe
                self._sync_subscriptions_from_djstripe()
                
                # Step 2: Link invoices to bookings
                self._sync_invoices_to_bookings()
                
                # Step 3: Use existing sync system if available for booking generation
                if LEGACY_SYNC_AVAILABLE:
                    self._integrate_with_legacy_sync(horizon_days)
                else:
                    # Fallback: generate bookings directly
                    self._generate_bookings_from_subscriptions(horizon_days)
                
                # Step 4: Update sync timestamps
                self._update_sync_timestamps()
                
                logger.info(f"Stripe sync completed successfully: {self.sync_stats}")
                return {
                    'success': True,
                    'stats': self.sync_stats,
                    'timestamp': timezone.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Stripe sync failed: {e}", exc_info=True)
            self.sync_stats['errors'].append(str(e))
            return {
                'success': False,
                'error': str(e),
                'stats': self.sync_stats,
                'timestamp': timezone.now().isoformat()
            }

    def _sync_subscriptions_from_djstripe(self):
        """Sync subscriptions from djstripe to our Django models"""
        logger.info("Syncing subscriptions from djstripe")
        
        # Get all active djstripe subscriptions
        # Note: djstripe stores status in stripe_data field
        djstripe_subscriptions = DjstripeSubscription.objects.all().select_related('customer')
        
        # Filter for active subscriptions based on stripe_data
        active_subscriptions = []
        for djstripe_sub in djstripe_subscriptions:
            stripe_data = djstripe_sub.stripe_data or {}
            status = stripe_data.get('status', '')
            if status in ['active', 'trialing', 'past_due']:
                active_subscriptions.append(djstripe_sub)
        
        logger.info(f"Found {len(active_subscriptions)} active subscriptions in djstripe")
        
        for djstripe_sub in active_subscriptions:
            try:
                # Get stripe data
                stripe_data = djstripe_sub.stripe_data or {}
                
                # Get or create the client
                client = self._get_or_create_client_from_djstripe_customer(djstripe_sub.customer)
                
                # Get or create subscription
                subscription, created = Subscription.objects.get_or_create(
                    stripe_subscription_id=djstripe_sub.id,
                    defaults={
                        'client': client,
                        'status': stripe_data.get('status', 'active'),
                        'created_from_stripe': True,
                        'stripe_created_at': djstripe_sub.created,
                        'service_code': self._extract_service_code_from_djstripe_subscription(djstripe_sub),
                        'service_name': self._extract_service_name_from_djstripe_subscription(djstripe_sub),
                        'schedule_days': self._extract_schedule_days_from_djstripe(djstripe_sub),
                        'schedule_start_time': self._extract_schedule_time_from_djstripe(djstripe_sub, 'start'),
                        'schedule_end_time': self._extract_schedule_time_from_djstripe(djstripe_sub, 'end'),
                        'schedule_location': djstripe_sub.metadata.get('location', ''),
                        'schedule_dogs': int(djstripe_sub.metadata.get('dogs', 1)),
                        'schedule_notes': djstripe_sub.metadata.get('notes', ''),
                    }
                )
                
                if created:
                    self.sync_stats['subscriptions_created'] += 1
                    logger.info(f"Created new subscription: {djstripe_sub.id}")
                else:
                    # Update existing subscription
                    subscription.status = stripe_data.get('status', 'active')
                    subscription.service_code = self._extract_service_code_from_djstripe_subscription(djstripe_sub)
                    subscription.service_name = self._extract_service_name_from_djstripe_subscription(djstripe_sub)
                    subscription.schedule_days = self._extract_schedule_days_from_djstripe(djstripe_sub)
                    subscription.schedule_start_time = self._extract_schedule_time_from_djstripe(djstripe_sub, 'start')
                    subscription.schedule_end_time = self._extract_schedule_time_from_djstripe(djstripe_sub, 'end')
                    subscription.schedule_location = djstripe_sub.metadata.get('location', '')
                    subscription.schedule_dogs = int(djstripe_sub.metadata.get('dogs', 1))
                    subscription.schedule_notes = djstripe_sub.metadata.get('notes', '')
                    subscription.save()
                    
                    self.sync_stats['subscriptions_updated'] += 1
                    logger.debug(f"Updated existing subscription: {djstripe_sub.id}")
                
                self.sync_stats['subscriptions_processed'] += 1
                
            except Exception as e:
                error_msg = f"Failed to sync subscription {djstripe_sub.id}: {e}"
                logger.error(error_msg)
                self.sync_stats['errors'].append(error_msg)

    def _sync_invoices_to_bookings(self):
        """Link Stripe invoices to existing bookings"""
        logger.info("Linking invoices to bookings")
        
        # Get recent invoices (last 90 days)
        since_date = timezone.now() - timedelta(days=90)
        djstripe_invoices = DjstripeInvoice.objects.filter(
            created__gte=since_date
        )
        
        # Filter for relevant invoice statuses
        relevant_invoices = []
        for djstripe_invoice in djstripe_invoices:
            stripe_data = djstripe_invoice.stripe_data or {}
            status = stripe_data.get('status', '')
            if status in ['paid', 'open']:
                relevant_invoices.append(djstripe_invoice)
        
        logger.info(f"Found {len(relevant_invoices)} relevant invoices")
        
        for djstripe_invoice in relevant_invoices:
            try:
                # Get stripe data
                stripe_data = djstripe_invoice.stripe_data or {}
                
                # Try to link invoice to bookings based on subscription
                subscription_id = stripe_data.get('subscription')
                if subscription_id:
                    # Find bookings from this subscription that don't have invoices yet
                    bookings = Booking.objects.filter(
                        created_from_sub_id=subscription_id,
                        stripe_invoice_id__isnull=True
                    ).order_by('start_dt')
                    
                    # Link the first unbilled booking to this invoice
                    if bookings.exists():
                        booking = bookings.first()
                        booking.stripe_invoice_id = djstripe_invoice.id
                        invoice_url = stripe_data.get('hosted_invoice_url')
                        if invoice_url:
                            booking.invoice_url = invoice_url
                        booking.save()
                        
                        self.sync_stats['invoices_linked'] += 1
                        logger.debug(f"Linked invoice {djstripe_invoice.id} to booking {booking.id}")
                
            except Exception as e:
                error_msg = f"Failed to link invoice {djstripe_invoice.id}: {e}"
                logger.error(error_msg)
                self.sync_stats['errors'].append(error_msg)

    def _integrate_with_legacy_sync(self, horizon_days: int):
        """Integrate with existing PySide6-based sync system"""
        logger.info("Integrating with legacy sync system")
        
        try:
            # Use existing sync function with SQLite connection
            with connection.cursor() as cursor:
                # Get raw SQLite connection for legacy sync
                sqlite_conn = cursor.connection
                
                # Call existing sync function
                legacy_stats = sync_subscriptions_to_bookings_and_calendar(
                    conn=sqlite_conn,
                    horizon_days=horizon_days
                )
                
                # Merge stats
                self.sync_stats['bookings_created'] += legacy_stats.get('bookings_created', 0)
                self.sync_stats['bookings_cleaned'] = legacy_stats.get('bookings_cleaned', 0)
                
                logger.info(f"Legacy sync completed: {legacy_stats}")
                
        except Exception as e:
            error_msg = f"Legacy sync integration failed: {e}"
            logger.error(error_msg)
            self.sync_stats['errors'].append(error_msg)

    def _generate_bookings_from_subscriptions(self, horizon_days: int):
        """Fallback method to generate bookings directly from Django subscriptions"""
        logger.info("Generating bookings from Django subscriptions (fallback)")
        
        active_subscriptions = Subscription.objects.filter(status='active')
        end_date = timezone.now() + timedelta(days=horizon_days)
        
        for subscription in active_subscriptions:
            try:
                # Parse schedule days
                days = subscription.schedule_days.split(',')
                day_mapping = {
                    'MON': 0, 'TUE': 1, 'WED': 2, 'THU': 3,
                    'FRI': 4, 'SAT': 5, 'SUN': 6
                }
                
                weekdays = [day_mapping[day.strip()] for day in days if day.strip() in day_mapping]
                
                # Generate occurrences
                current_date = timezone.now().date()
                while current_date <= end_date.date():
                    if current_date.weekday() in weekdays:
                        # Create datetime for booking
                        start_dt = timezone.datetime.combine(
                            current_date,
                            subscription.schedule_start_time
                        )
                        start_dt = timezone.make_aware(start_dt)
                        
                        end_dt = timezone.datetime.combine(
                            current_date,
                            subscription.schedule_end_time
                        )
                        end_dt = timezone.make_aware(end_dt)
                        
                        # Check if booking already exists
                        if not Booking.objects.filter(
                            created_from_sub_id=subscription.stripe_subscription_id,
                            start_dt=start_dt
                        ).exists():
                            # Create booking
                            booking = Booking.objects.create(
                                client=subscription.client,
                                subscription=subscription,
                                created_from_sub_id=subscription.stripe_subscription_id,
                                start_dt=start_dt,
                                end_dt=end_dt,
                                service_type=subscription.service_code,
                                service_name=subscription.service_name,
                                location=subscription.schedule_location,
                                dogs=subscription.schedule_dogs,
                                notes=subscription.schedule_notes,
                                source='subscription',
                                status='scheduled'
                            )
                            
                            self.sync_stats['bookings_created'] += 1
                            logger.debug(f"Created booking for {start_dt}")
                    
                    current_date += timedelta(days=1)
                    
            except Exception as e:
                error_msg = f"Failed to generate bookings for subscription {subscription.stripe_subscription_id}: {e}"
                logger.error(error_msg)
                self.sync_stats['errors'].append(error_msg)

    def _get_or_create_client_from_djstripe_customer(self, djstripe_customer: DjstripeCustomer) -> Client:
        """Get or create a Client from djstripe Customer data"""
        # Get customer data from stripe_data
        stripe_data = djstripe_customer.stripe_data or {}
        
        client, created = Client.objects.get_or_create(
            stripe_customer_id=djstripe_customer.id,
            defaults={
                'name': stripe_data.get('description') or stripe_data.get('email') or f'Customer {djstripe_customer.id}',
                'email': stripe_data.get('email'),
                'phone': stripe_data.get('phone'),
                'address': self._format_customer_address_from_stripe_data(stripe_data),
                'acquisition_date': timezone.now(),
            }
        )
        
        if created:
            self.sync_stats['clients_created'] += 1
            logger.debug(f"Created new client for customer: {djstripe_customer.id}")
        else:
            # Update client info if changed
            current_email = stripe_data.get('email')
            if current_email and client.email != current_email:
                client.email = current_email
                client.save()
                self.sync_stats['clients_updated'] += 1
        
        return client

    def _format_customer_address_from_stripe_data(self, stripe_data: dict) -> str:
        """Format customer address from Stripe data"""
        address = stripe_data.get('address', {})
        if isinstance(address, dict):
            parts = [
                address.get('line1', ''),
                address.get('line2', ''),
                address.get('city', ''),
                address.get('state', ''),
                address.get('postal_code', ''),
                address.get('country', '')
            ]
            return ', '.join(part for part in parts if part)
        return str(address) if address else ''

    def _extract_service_code_from_djstripe_subscription(self, subscription: DjstripeSubscription) -> str:
        """Extract service code from djstripe subscription metadata"""
        # Check metadata first
        service_code = subscription.metadata.get('service_code') or subscription.metadata.get('service')
        if service_code:
            return service_code
            
        # Try to get from items/prices
        stripe_data = subscription.stripe_data or {}
        items = stripe_data.get('items', {}).get('data', [])
        
        for item in items:
            price_data = item.get('price', {})
            price_metadata = price_data.get('metadata', {})
            service_code = price_metadata.get('service_code') or price_metadata.get('service')
            if service_code:
                return service_code
        
        # Default service code
        return 'DOG_WALK_30'

    def _extract_service_name_from_djstripe_subscription(self, subscription: DjstripeSubscription) -> str:
        """Extract service name from djstripe subscription metadata"""
        service_name = subscription.metadata.get('service_name')
        if service_name:
            return service_name
            
        # Try to get from items/prices
        stripe_data = subscription.stripe_data or {}
        items = stripe_data.get('items', {}).get('data', [])
        
        for item in items:
            price_data = item.get('price', {})
            product_data = price_data.get('product', {})
            
            # Check product name
            if isinstance(product_data, dict):
                product_name = product_data.get('name')
                if product_name:
                    return product_name
        
        return 'Dog Walking Service'

    def _extract_schedule_days_from_djstripe(self, subscription: DjstripeSubscription) -> str:
        """Extract schedule days from djstripe subscription metadata"""
        days = subscription.metadata.get('days', '')
        if days:
            return days.upper()
        return 'MON,WED,FRI'  # Default

    def _extract_schedule_time_from_djstripe(self, subscription: DjstripeSubscription, time_type: str) -> timezone.datetime.time:
        """Extract schedule time from djstripe subscription metadata"""
        time_str = subscription.metadata.get(f'{time_type}_time', '')
        if time_str:
            try:
                # Parse time string (HH:MM format)
                hour, minute = map(int, time_str.split(':'))
                return timezone.datetime.time(hour, minute)
            except (ValueError, AttributeError):
                pass
        
        # Default times
        if time_type == 'start':
            return timezone.datetime.time(9, 0)  # 9:00 AM
        else:
            return timezone.datetime.time(9, 30)  # 9:30 AM

    def _update_sync_timestamps(self):
        """Update last_sync_at for all processed subscriptions"""
        sync_time = timezone.now()
        Subscription.objects.all().update(last_sync_at=sync_time)
        logger.debug("Updated sync timestamps for all subscriptions")


# Singleton service instance
stripe_sync_service = StripeSyncService()


def sync_stripe_data_on_startup(horizon_days: int = 90) -> Dict[str, Any]:
    """
    Entry point for startup sync called from Django app ready() method.
    
    Args:
        horizon_days: Number of days ahead to generate bookings
        
    Returns:
        Dictionary with sync results
    """
    logger.info("Starting startup Stripe sync")
    return stripe_sync_service.sync_all_stripe_data(horizon_days)