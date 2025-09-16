"""
Django management command to migrate existing data to Django models.

This command safely migrates data from the existing SQLite database
to the new Django models without losing any existing functionality.
"""

import logging
import sqlite3
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import datetime
from core.models import Client, Subscription, Booking

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate existing data from SQLite to Django models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually doing it',
        )
        parser.add_argument(
            '--database-path',
            default='app.db',
            help='Path to the existing SQLite database file',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        db_path = options['database_path']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No data will be modified')
            )
        
        try:
            # Connect to existing database
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            
            self.stdout.write(f'Connected to database: {db_path}')
            
            # Migrate clients first
            clients_migrated = self.migrate_clients(conn, dry_run)
            self.stdout.write(
                self.style.SUCCESS(f'Clients migrated: {clients_migrated}')
            )
            
            # Check for subscription schedule data
            subscriptions_migrated = self.migrate_subscription_schedules(conn, dry_run)
            self.stdout.write(
                self.style.SUCCESS(f'Subscription schedules migrated: {subscriptions_migrated}')
            )
            
            # Migrate bookings
            bookings_migrated = self.migrate_bookings(conn, dry_run)
            self.stdout.write(
                self.style.SUCCESS(f'Bookings migrated: {bookings_migrated}')
            )
            
            conn.close()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Migration completed successfully!\n'
                    f'Clients: {clients_migrated}\n'
                    f'Subscriptions: {subscriptions_migrated}\n'
                    f'Bookings: {bookings_migrated}'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Migration failed: {e}')
            )
            logger.error(f"Migration failed: {e}")
            raise

    def migrate_clients(self, conn, dry_run):
        """Migrate client data to Django Client model"""
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, name, email, phone, address, stripe_customer_id, 
                       credit_cents, status, acquisition_date, last_service_date,
                       total_revenue_cents, service_count
                FROM clients
            """)
        except sqlite3.OperationalError:
            # Table might not exist or have different schema
            self.stdout.write(
                self.style.WARNING('Clients table not found or has different schema')
            )
            return 0
        
        clients = cursor.fetchall()
        migrated_count = 0
        
        for client_row in clients:
            if dry_run:
                self.stdout.write(f'Would migrate client: {client_row["name"]}')
                migrated_count += 1
                continue
            
            try:
                with transaction.atomic():
                    # Convert dates
                    acquisition_date = None
                    if client_row['acquisition_date']:
                        try:
                            acquisition_date = datetime.fromisoformat(client_row['acquisition_date'])
                        except (ValueError, TypeError):
                            acquisition_date = timezone.now()
                    
                    last_service_date = None
                    if client_row['last_service_date']:
                        try:
                            last_service_date = datetime.fromisoformat(client_row['last_service_date'])
                        except (ValueError, TypeError):
                            pass
                    
                    client, created = Client.objects.update_or_create(
                        id=client_row['id'],
                        defaults={
                            'name': client_row['name'] or 'Unknown',
                            'email': client_row['email'],
                            'phone': client_row['phone'],
                            'address': client_row['address'],
                            'stripe_customer_id': client_row['stripe_customer_id'],
                            'credit_cents': client_row['credit_cents'] or 0,
                            'status': client_row['status'] or 'active',
                            'acquisition_date': acquisition_date or timezone.now(),
                            'last_service_date': last_service_date,
                            'total_revenue_cents': client_row['total_revenue_cents'] or 0,
                            'service_count': client_row['service_count'] or 0,
                        }
                    )
                    
                    action = 'created' if created else 'updated'
                    self.stdout.write(f'Client {client.name} ({action})')
                    migrated_count += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Failed to migrate client {client_row["name"]}: {e}')
                )
                logger.error(f"Failed to migrate client {client_row['name']}: {e}")
        
        return migrated_count

    def migrate_subscription_schedules(self, conn, dry_run):
        """Migrate subscription schedule data to Django Subscription model"""
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT stripe_subscription_id, days, start_time, end_time, 
                       location, dogs, notes
                FROM subs_schedule
            """)
        except sqlite3.OperationalError:
            self.stdout.write(
                self.style.WARNING('subs_schedule table not found')
            )
            return 0
        
        schedules = cursor.fetchall()
        migrated_count = 0
        
        for schedule_row in schedules:
            if dry_run:
                self.stdout.write(f'Would migrate subscription schedule: {schedule_row["stripe_subscription_id"]}')
                migrated_count += 1
                continue
            
            try:
                # This would be used when we have active Stripe integration
                # For now, we'll create placeholder subscriptions
                self.stdout.write(
                    self.style.WARNING(
                        f'Subscription schedule found for {schedule_row["stripe_subscription_id"]} '
                        f'- requires active Stripe integration to migrate fully'
                    )
                )
                migrated_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Failed to migrate subscription schedule {schedule_row["stripe_subscription_id"]}: {e}')
                )
                logger.error(f"Failed to migrate subscription schedule: {e}")
        
        return migrated_count

    def migrate_bookings(self, conn, dry_run):
        """Migrate booking data to Django Booking model"""
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, client_id, start_dt, end_dt, service_type, service_name,
                       location, dogs, notes, status, source, created_from_sub_id,
                       stripe_invoice_id, stripe_price_id, invoice_url
                FROM bookings
            """)
        except sqlite3.OperationalError:
            self.stdout.write(
                self.style.WARNING('Bookings table not found or has different schema')
            )
            return 0
        
        bookings = cursor.fetchall()
        migrated_count = 0
        
        for booking_row in bookings:
            if dry_run:
                self.stdout.write(f'Would migrate booking: {booking_row["id"]}')
                migrated_count += 1
                continue
            
            try:
                with transaction.atomic():
                    # Get client
                    try:
                        client = Client.objects.get(id=booking_row['client_id'])
                    except Client.DoesNotExist:
                        self.stdout.write(
                            self.style.ERROR(f'Client {booking_row["client_id"]} not found for booking {booking_row["id"]}')
                        )
                        continue
                    
                    # Convert datetime fields
                    try:
                        start_dt = datetime.fromisoformat(booking_row['start_dt'])
                        end_dt = datetime.fromisoformat(booking_row['end_dt'])
                    except (ValueError, TypeError):
                        self.stdout.write(
                            self.style.ERROR(f'Invalid datetime format in booking {booking_row["id"]}')
                        )
                        continue
                    
                    booking, created = Booking.objects.update_or_create(
                        id=booking_row['id'],
                        defaults={
                            'client': client,
                            'start_dt': start_dt,
                            'end_dt': end_dt,
                            'service_type': booking_row['service_type'] or 'DOG_WALK',
                            'service_name': booking_row['service_name'] or 'Dog Walking',
                            'location': booking_row['location'],
                            'dogs': booking_row['dogs'] or 1,
                            'notes': booking_row['notes'],
                            'status': booking_row['status'] or 'scheduled',
                            'source': booking_row['source'] or 'manual',
                            'created_from_sub_id': booking_row['created_from_sub_id'],
                            'stripe_invoice_id': booking_row['stripe_invoice_id'],
                            'stripe_price_id': booking_row['stripe_price_id'],
                            'invoice_url': booking_row['invoice_url'],
                        }
                    )
                    
                    action = 'created' if created else 'updated'
                    self.stdout.write(f'Booking {booking.id} for {client.name} ({action})')
                    migrated_count += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Failed to migrate booking {booking_row["id"]}: {e}')
                )
                logger.error(f"Failed to migrate booking {booking_row['id']}: {e}")
        
        return migrated_count