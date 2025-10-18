from django.core.management.base import BaseCommand
from datetime import timedelta
from core.models import Booking, SubOccurrence


class Command(BaseCommand):
    help = "Create missing bookings for SubOccurrence entries which now have a service with duration."

    def handle(self, *args, **options):
        created = 0
        skipped = 0
        qs = (SubOccurrence.objects
              .select_related("service")
              .order_by("start_dt"))
        
        for occ in qs:
            if not occ.service or not occ.service.duration_minutes:
                skipped += 1
                continue
            
            # Get client from the subscription link
            from core.models import StripeSubscriptionLink
            try:
                sub_link = StripeSubscriptionLink.objects.get(stripe_subscription_id=occ.stripe_subscription_id)
                client = sub_link.client
            except StripeSubscriptionLink.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"No subscription link found for {occ.stripe_subscription_id}"))
                skipped += 1
                continue
            
            if Booking.objects.filter(client=client, start_dt=occ.start_dt).exists():
                continue
            
            end_dt = occ.start_dt + timedelta(minutes=occ.service.duration_minutes)
            Booking.objects.create(
                client=client,
                service=occ.service,
                service_code=sub_link.service_code,
                service_name=occ.service.name,
                service_label=occ.service.name,
                start_dt=occ.start_dt,
                end_dt=end_dt,
                location="",
                dogs=1,
                status="confirmed",
                price_cents=0,
                stripe_invoice_id=None,
                notes="Backfilled from occurrence after setting service duration",
            )
            created += 1
        
        self.stdout.write(self.style.SUCCESS(f"Backfill complete. created={created} skipped={skipped}"))
