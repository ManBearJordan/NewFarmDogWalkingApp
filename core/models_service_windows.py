"""
Service Windows model for managing time-based service availability constraints.
"""
from __future__ import annotations
from django.db import models
from django.utils import timezone


WEEKDAY_CHOICES = [(i, d) for i, d in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])]
ALL_DAYS = -1


class ServiceWindow(models.Model):
    """
    A window that reserves time for specific services and/or constrains others.
    - If block_in_portal=True: client bookings for services NOT in allowed_services
      are blocked during this window.
    - warn_in_admin=True: admin calendar will warn on bookings that violate.
    - max_concurrent: optional capacity cap; if >0, admin warns when exceeded.
    """
    title = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    weekday = models.SmallIntegerField(
        choices=[(ALL_DAYS, "All days")] + WEEKDAY_CHOICES, default=ALL_DAYS
    )
    start_time = models.TimeField()
    end_time = models.TimeField()

    allowed_services = models.ManyToManyField(
        "core.Service", blank=True, related_name="allowed_windows"
    )

    block_in_portal = models.BooleanField(default=True)
    warn_in_admin = models.BooleanField(default=True)
    max_concurrent = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Optional. 0 or blank disables capacity check."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("weekday", "start_time", "title")

    def __str__(self):
        wd = "All" if self.weekday == ALL_DAYS else WEEKDAY_CHOICES[self.weekday][1]
        return f"{self.title} [{wd} {self.start_time}-{self.end_time}]"

    # ---- helpers ----
    def applies_on(self, dt: timezone.datetime) -> bool:
        """Check if this window applies on the given datetime's weekday."""
        if not self.active:
            return False
        if self.weekday == ALL_DAYS:
            return True
        # Monday=0 ... Sunday=6 (Django matches Python)
        return dt.weekday() == self.weekday

    def overlaps(self, start_dt, end_dt) -> bool:
        """Compare by local times-of-day; ignore date for daily windows."""
        local = timezone.localtime
        s = local(start_dt).timetz()
        e = local(end_dt).timetz()
        # simple non-wrapping windows (08:30–10:30 etc.)
        return (self.start_time < e) and (self.end_time > s)

    def blocks_service_in_portal(self, service) -> bool:
        """
        Returns True if this window blocks the given service for portal bookings.
        """
        if not self.block_in_portal:
            return False
        if not self.allowed_services.exists():
            # if no allowed list configured, treat as no block
            return False
        return service.pk not in self.allowed_services.values_list("pk", flat=True)
