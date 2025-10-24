"""
Management command to seed default Service Windows for Group Walks.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models_service_windows import ServiceWindow


class Command(BaseCommand):
    help = "Seeds default Group Walk windows (08:30–10:30 and 14:30–16:30). Edit allowed services in admin."

    def handle(self, *args, **opts):
        def upsert(title, start, end):
            obj, created = ServiceWindow.objects.get_or_create(
                title=title,
                weekday=-1,
                start_time=start,
                end_time=end,
                defaults={
                    "block_in_portal": True,
                    "warn_in_admin": True,
                    "active": True,
                },
            )
            status = "Created" if created else "Already exists"
            self.stdout.write(f"{status}: {obj}")
        
        # Create AM and PM group walk windows
        from datetime import time
        upsert("Group Walk AM", time(8, 30), time(10, 30))
        upsert("Group Walk PM", time(14, 30), time(16, 30))
        
        self.stdout.write(self.style.SUCCESS(
            "Seeded. Now open Admin → Service windows and configure allowed services for each window."
        ))
