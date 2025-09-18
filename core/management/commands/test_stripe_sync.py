"""
Django management command to test the Stripe sync system.
"""

import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from core.services.stripe_sync import sync_stripe_data_on_startup

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test the Stripe sync system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in dry-run mode without making changes',
        )
        parser.add_argument(
            '--horizon-days',
            type=int,
            default=90,
            help='Number of days ahead to generate bookings (default: 90)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        horizon_days = options['horizon_days']
        
        self.stdout.write('Testing Stripe sync system...')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in DRY-RUN mode - no changes will be made'))
        
        try:
            if dry_run:
                # Test without making changes
                self.stdout.write('Testing sync service import...')
                from core.services.stripe_sync import stripe_sync_service
                self.stdout.write(self.style.SUCCESS('✓ Sync service imported successfully'))
                
                # Test djstripe import
                self.stdout.write('Testing djstripe imports...')
                from djstripe.models import Subscription, Invoice, Customer
                self.stdout.write(self.style.SUCCESS('✓ djstripe models imported successfully'))
                
                # Test Django models
                self.stdout.write('Testing Django models...')
                from core.models import Client, Subscription, Booking
                self.stdout.write(self.style.SUCCESS('✓ Django models imported successfully'))
                
                # Test database connectivity
                self.stdout.write('Testing database connectivity...')
                client_count = Client.objects.count()
                subscription_count = Subscription.objects.count()
                booking_count = Booking.objects.count()
                
                self.stdout.write(f'✓ Database accessible - Clients: {client_count}, Subscriptions: {subscription_count}, Bookings: {booking_count}')
                
            else:
                # Run actual sync
                self.stdout.write(f'Running Stripe sync with {horizon_days} day horizon...')
                
                result = sync_stripe_data_on_startup(horizon_days=horizon_days)
                
                if result.get('success'):
                    stats = result.get('stats', {})
                    self.stdout.write(self.style.SUCCESS('Sync completed successfully!'))
                    self.stdout.write('Sync statistics:')
                    for key, value in stats.items():
                        if key == 'errors' and value:
                            self.stdout.write(f'  {key}: {len(value)} error(s)')
                            for error in value[:5]:  # Show first 5 errors
                                self.stdout.write(f'    - {error}')
                        else:
                            self.stdout.write(f'  {key}: {value}')
                else:
                    error = result.get('error', 'Unknown error')
                    self.stdout.write(self.style.ERROR(f'Sync failed: {error}'))
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Test failed: {e}'))
            logger.error(f"Stripe sync test failed: {e}", exc_info=True)