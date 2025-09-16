"""
Django management command to sync subscriptions with Stripe.

This command provides a Django interface to the existing subscription
sync functionality, making it available for cron jobs and administration.
"""

import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from core.tasks import sync_all_subscriptions, sync_single_subscription

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync subscriptions with Stripe'

    def add_arguments(self, parser):
        parser.add_argument(
            '--subscription-id',
            help='Sync a specific subscription by Stripe subscription ID',
        )
        parser.add_argument(
            '--horizon-days',
            type=int,
            default=90,
            help='Number of days ahead to generate bookings (default: 90)',
        )
        parser.add_argument(
            '--async',
            action='store_true',
            help='Run sync as background task (requires Celery)',
        )

    def handle(self, *args, **options):
        subscription_id = options.get('subscription_id')
        horizon_days = options['horizon_days']
        run_async = options['async']
        
        if subscription_id:
            self.sync_single_subscription(subscription_id, run_async)
        else:
            self.sync_all_subscriptions(horizon_days, run_async)

    def sync_single_subscription(self, subscription_id, run_async):
        """Sync a single subscription"""
        self.stdout.write(f'Syncing subscription: {subscription_id}')
        
        if run_async:
            # Run as background task
            task = sync_single_subscription.delay(subscription_id)
            self.stdout.write(
                self.style.SUCCESS(f'Sync task queued with ID: {task.id}')
            )
        else:
            # Run synchronously
            try:
                from subscription_sync import sync_on_subscription_change
                
                result = sync_on_subscription_change(subscription_id)
                
                self.stdout.write(
                    self.style.SUCCESS(f'Subscription sync completed: {result}')
                )
                
                # Update Django model if it exists
                from core.models import Subscription
                try:
                    subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
                    subscription.last_sync_at = timezone.now()
                    subscription.save()
                    self.stdout.write('Updated Django model sync timestamp')
                except Subscription.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING('Subscription not found in Django models')
                    )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Sync failed: {e}')
                )
                logger.error(f"Subscription sync failed: {e}")
                raise

    def sync_all_subscriptions(self, horizon_days, run_async):
        """Sync all active subscriptions"""
        self.stdout.write(f'Syncing all subscriptions (horizon: {horizon_days} days)')
        
        if run_async:
            # Run as background task
            task = sync_all_subscriptions.delay(horizon_days)
            self.stdout.write(
                self.style.SUCCESS(f'Sync task queued with ID: {task.id}')
            )
        else:
            # Run synchronously
            try:
                from subscription_sync import sync_subscriptions_to_bookings_and_calendar
                
                result = sync_subscriptions_to_bookings_and_calendar(horizon_days=horizon_days)
                
                self.stdout.write(
                    self.style.SUCCESS(f'All subscriptions sync completed: {result}')
                )
                
                # Update Django models
                from core.models import Subscription
                active_subscriptions = Subscription.objects.filter(status='active')
                updated_count = active_subscriptions.update(last_sync_at=timezone.now())
                
                self.stdout.write(f'Updated {updated_count} Django subscription models')
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Sync failed: {e}')
                )
                logger.error(f"All subscriptions sync failed: {e}")
                raise