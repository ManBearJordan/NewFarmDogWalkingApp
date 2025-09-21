"""Django management command to sync subscriptions."""

from django.core.management.base import BaseCommand, CommandError
from core.subscription_sync import sync_subscriptions_to_bookings_and_calendar


class Command(BaseCommand):
    help = 'Sync Stripe subscriptions to SubOccurrence records'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--horizon-days',
            type=int,
            default=90,
            help='Number of days to look ahead for subscription occurrences (default: 90)'
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Minimize output (only show final stats)'
        )
    
    def handle(self, *args, **options):
        horizon_days = options['horizon_days']
        quiet = options['quiet']
        
        if horizon_days <= 0:
            raise CommandError('horizon-days must be a positive integer')
        
        if not quiet:
            self.stdout.write(f'Starting subscription sync with horizon of {horizon_days} days...')
        
        try:
            result = sync_subscriptions_to_bookings_and_calendar(horizon_days=horizon_days)
            
            # Print stats
            self.stdout.write(
                self.style.SUCCESS(
                    f'Sync completed successfully:\n'
                    f'  Processed: {result["processed"]} subscriptions\n'
                    f'  Created: {result["created"]} new SubOccurrence records\n'
                    f'  Cleaned: {result["cleaned"]} old SubOccurrence records\n'
                    f'  Errors: {result["errors"]} errors encountered'
                )
            )
            
            if result['errors'] > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'Warning: {result["errors"]} errors occurred during sync. '
                        'Check subscription_error_log.txt for details.'
                    )
                )
            
        except Exception as e:
            raise CommandError(f'Sync failed: {e}')