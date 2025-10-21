from django.core.management.base import BaseCommand
from core.stripe_invoices_sync import sync_invoices


class Command(BaseCommand):
    help = "Sync recent Stripe invoices into local bookings; updates invoice fields and flags mismatches."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=90, help="Look back this many days (default 90)")

    def handle(self, *args, **options):
        days = options["days"]
        res = sync_invoices(days=days)
        self.stdout.write(self.style.SUCCESS(f"sync_invoices complete: {res}"))
