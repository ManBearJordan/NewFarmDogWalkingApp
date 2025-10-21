from django.core.management.base import BaseCommand
from django.core.management import call_command, get_commands
from core.subscription_materializer import materialize_future_holds


class Command(BaseCommand):
    help = "Run all Stripe/data sync steps in a safe order."

    def handle(self, *args, **opts):
        # Execute only the commands that actually exist in this install
        def maybe(cmd):
            if cmd in get_commands():
                call_command(cmd)
            else:
                self.stdout.write(self.style.WARNING(f"Skipping {cmd}: not installed."))
        maybe("sync_customers")
        maybe("sync_subscriptions")
        maybe("build_bookings_from_invoices")
        maybe("build_bookings_from_subscriptions")
        
        # Run materializer
        result = materialize_future_holds()
        self.stdout.write(self.style.SUCCESS(f"Materialization complete: created {result.get('created', 0)} bookings."))
        
        self.stdout.write(self.style.SUCCESS("sync_all complete."))
