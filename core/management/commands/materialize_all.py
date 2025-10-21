from django.core.management.base import BaseCommand
from django.utils import timezone
from core.subscription_materializer import materialize_all


class Command(BaseCommand):
    help = "Deterministically (re)materialize future bookings for all schedules (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--weeks", type=int, default=12, help="Horizon in weeks (default 12)")

    def handle(self, *args, **options):
        weeks = options["weeks"]
        self.stdout.write(f"Materializing bookings for {weeks} weeks ahead...")
        res = materialize_all(now_dt=timezone.localtime(), horizon_weeks=weeks)
        self.stdout.write(self.style.SUCCESS(f"Materialization complete: {res}"))
