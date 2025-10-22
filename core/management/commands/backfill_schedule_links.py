from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.timezone import make_naive, is_aware
from zoneinfo import ZoneInfo
from core.models import Booking, StripeSubscriptionSchedule, Service

BRISBANE = ZoneInfo("Australia/Brisbane")


class Command(BaseCommand):
    help = "Attach schedule FK to bookings when a unique WEEKLY schedule deterministically matches the slot. Fortnightly is skipped (ambiguous without anchor)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show changes without writing.")
        parser.add_argument("--limit", type=int, default=0, help="Process at most N rows (0 = no limit).")

    @transaction.atomic
    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        limit = opts["limit"]
        qs = (Booking.objects
              .select_related("client", "service")
              .filter(schedule__isnull=True)
              .order_by("id"))
        linked = 0
        scanned = 0
        for b in qs.iterator():
            scanned += 1
            if limit and scanned > limit:
                break
            svc = b.service
            if not svc:
                continue
            # Convert to naive local datetime for matching
            start_dt = b.start_dt
            if is_aware(start_dt):
                start_dt = make_naive(start_dt.astimezone(BRISBANE), BRISBANE)
            # Candidate schedules: same client, same service_code, active & complete
            candidates = (StripeSubscriptionSchedule.objects
                          .filter(sub__client=b.client,
                                  sub__service_code=svc.code,
                                  sub__active=True))
            candidates = [s for s in candidates if s.is_complete() and s.occurs_on_datetime(start_dt)]
            if len(candidates) == 1:
                sched = candidates[0]
                self.stdout.write(f"Link booking #{b.id} -> schedule #{sched.id}")
                linked += 1
                if not dry:
                    b.schedule = sched
                    b.save(update_fields=["schedule"])
            else:
                # Either none or ambiguous (2+), skip to avoid wrong linkage
                continue
        self.stdout.write(self.style.SUCCESS(f"Scanned={scanned}, Linked={linked}, DryRun={dry}"))
