from django.core.management.base import BaseCommand
from core.stripe_invoices_sync import sync_invoices


class Command(BaseCommand):
    help = "Alias for invoice backfill: pull recent Stripe invoices and update/link bookings (uses PR-9 engine)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=90, help="Look back this many days (default 90)")

    def handle(self, *args, **options):
        days = options["days"]
        res = sync_invoices(days=days)
        self.stdout.write(self.style.SUCCESS(f"backfill_invoice_links complete: {res}"))
