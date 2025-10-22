from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Booking


class Command(BaseCommand):
    help = "Repair bookings missing end_dt or with wrong duration by recomputing from Service.duration_minutes."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would change, but do not write.")
        parser.add_argument("--limit", type=int, default=0, help="Process at most N rows (0 = no limit).")

    @transaction.atomic
    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        limit = opts["limit"]
        qs = (Booking.objects
              .select_related("service")
              .order_by("id"))
        fixed = 0
        scanned = 0
        for b in qs.iterator():
            scanned += 1
            if limit and scanned > limit:
                break
            svc = b.service
            if not svc or not svc.duration_minutes:
                continue
            desired_end = b.start_dt + timedelta(minutes=svc.duration_minutes)
            if not b.end_dt or b.end_dt != desired_end:
                self.stdout.write(f"Fix #{b.id}: {b.end_dt} -> {desired_end}")
                fixed += 1
                if not dry:
                    b.end_dt = desired_end
                    b.save(update_fields=["end_dt"])
        self.stdout.write(self.style.SUCCESS(f"Scanned={scanned}, Fixed end_dt={fixed}, DryRun={dry}"))
