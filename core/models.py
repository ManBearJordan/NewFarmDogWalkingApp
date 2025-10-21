from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid
from django.core.validators import RegexValidator


class Service(models.Model):
    """
    A walk/visit product with a configured default duration (in minutes).
    """
    code = models.SlugField(max_length=50, unique=True, help_text="Short code used by schedules/subscriptions (e.g., 'walk30').")
    name = models.CharField(max_length=120)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True, help_text="Length in minutes. Must be set before auto-bookings can be created.")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        dur = f" — {self.duration_minutes}m" if self.duration_minutes else ""
        return f"{self.name}{dur}"


class StripeSettings(models.Model):
    """Optional admin-surfaceable Stripe key; runtime prefers environment or keyring."""
    stripe_secret_key = models.CharField(max_length=200, blank=True, null=True)
    is_live_mode = models.BooleanField(default=False)

    def __str__(self):
        return f"Stripe Settings ({'Live' if self.is_live_mode else 'Test'})"

    @classmethod
    def get_stripe_key(cls):
        try:
            obj = cls.objects.first()
            return obj.stripe_secret_key if obj else None
        except Exception:
            return None

    @classmethod
    def set_stripe_key(cls, api_key):
        try:
            obj, created = cls.objects.get_or_create(defaults={'stripe_secret_key': api_key})
            if not created:
                obj.stripe_secret_key = api_key
                obj.save()
            return True
        except Exception:
            return False


class Client(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True, max_length=254)
    phone = models.CharField(max_length=20)
    address = models.TextField()
    notes = models.TextField(blank=True)
    credit_cents = models.IntegerField(default=0)
    status = models.CharField(max_length=50)
    stripe_customer_id = models.CharField(max_length=200, blank=True, null=True)
    # CRM tags
    # Note: Tag is declared below; use string reference to avoid reorder issues.
    tags = models.ManyToManyField("Tag", blank=True, related_name="clients")
    # Optional login for client portal (each client can have a single user)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="client_profile",
    )
    # Portal account controls
    can_self_reschedule = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class StripeKeyAudit(models.Model):
    """
    Record when a staff user updates the Stripe key via the admin UI.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    when = models.DateTimeField(default=timezone.now, db_index=True)
    previous_mode = models.CharField(max_length=32, null=True, blank=True)
    new_mode = models.CharField(max_length=32, null=True, blank=True)
    previous_test_or_live = models.CharField(max_length=16, null=True, blank=True)
    new_test_or_live = models.CharField(max_length=16, null=True, blank=True)
    note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-when"]

    def __str__(self):
        who = getattr(self.user, "username", "unknown")
        return f"StripeKey change by {who} at {self.when.isoformat()}"


class Pet(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    species = models.CharField(max_length=50, default='dog')
    breed = models.CharField(max_length=100, blank=True)
    medications = models.TextField(blank=True)
    behaviour = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.client.name})"


class Booking(models.Model):
    # ...
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    service = models.ForeignKey('Service', on_delete=models.PROTECT, null=True, blank=True)
    service_code = models.CharField(max_length=50)
    service_name = models.CharField(max_length=200)
    service_label = models.CharField(max_length=200)
    # Optional, to reflect the chosen block in the flexible timetable
    block_label = models.CharField(max_length=128, blank=True, null=True)
    start_dt = models.DateTimeField()
    end_dt = models.DateTimeField()
    location = models.CharField(max_length=200)
    dogs = models.IntegerField(default=1)
    status = models.CharField(max_length=50)
    price_cents = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    stripe_invoice_id = models.CharField(max_length=200, blank=True, null=True)
    deleted = models.BooleanField(default=False)
    # Card payments (portal flow)
    payment_intent_id = models.CharField(max_length=128, blank=True, null=True)
    charge_id = models.CharField(max_length=128, blank=True, null=True)
    # External key for syncing from Stripe (subscriptions/invoices)
    external_key = models.CharField(max_length=200, blank=True, null=True, unique=True, db_index=True)

    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
        ('void', 'Voided'),
        ('failed', 'Failed'),
    ]
    payment_status = models.CharField(max_length=16, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    invoice_pdf_url = models.URLField(blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    def mark_paid(self, when=None):
        self.payment_status = 'paid'
        self.paid_at = when or timezone.now()
        self.save(update_fields=['payment_status', 'paid_at'])

    def __str__(self):
        return f"{self.service_name} for {self.client.name} on {self.start_dt.date()}"


class BookingPet(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE)
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('booking', 'pet')

    def __str__(self):
        return f"{self.pet.name} in {self.booking}"


class AdminEvent(models.Model):
    due_dt = models.DateTimeField()
    title = models.CharField(max_length=200)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.title} (due {self.due_dt.date()})"

    @classmethod
    def log(cls, event_type, message):
        """
        Create an AdminEvent for alerting admins about system events.
        Due date is set to now for immediate visibility.
        Prevents duplicate logging by checking for recent similar events.
        """
        from django.utils import timezone
        # Check if a similar event was logged recently (within last hour)
        one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
        recent_event = cls.objects.filter(
            title__icontains=event_type,
            notes=message,
            due_dt__gte=one_hour_ago
        ).first()
        
        if not recent_event:
            cls.objects.create(
                due_dt=timezone.now(),
                title=f"{event_type}",
                notes=message
            )


class SubOccurrence(models.Model):
    id = models.AutoField(primary_key=True)
    stripe_subscription_id = models.CharField(max_length=64)
    start_dt = models.DateTimeField()
    end_dt = models.DateTimeField()
    active = models.BooleanField(default=True)
    service = models.ForeignKey('Service', on_delete=models.PROTECT, null=True, blank=True,
                                help_text="Service for this occurrence; determines duration for generated booking.")

    def __str__(self):
        return f"Sub {self.stripe_subscription_id} ({self.start_dt.date()} - {self.end_dt.date()})"


class StripeSubscriptionLink(models.Model):
    """
    Links a Stripe subscription to a client & service in our system.
    Discovered via API/webhook. One Link per Stripe subscription id.
    """
    stripe_subscription_id = models.CharField(max_length=64, unique=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="stripe_subs")
    service_code = models.CharField(max_length=64)  # mapped from product/price nickname/metadata
    status = models.CharField(max_length=32, default="active")  # active, canceled, paused
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    weekday = models.IntegerField(blank=True, null=True, help_text="0=Mon ... 6=Sun")
    time_of_day = models.TimeField(blank=True, null=True)  # local time
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"Sub {self.stripe_subscription_id} - {self.client.name} - {self.service_code}"


class StripeSubscriptionSchedule(models.Model):
    """
    One-time setup per Stripe subscription: which weekdays and a default time/block label.
    Weekdays stored as csv: 'mon,tue,fri'
    default_time in HH:MM 24h (local AEST)
    """
    sub = models.OneToOneField(StripeSubscriptionLink, on_delete=models.CASCADE, related_name="schedule")
    weekdays_csv = models.CharField(max_length=64, help_text="e.g. mon,tue,wed")
    default_time = models.CharField(
        max_length=5,
        validators=[RegexValidator(r"^\d{2}:\d{2}$")],
        help_text="HH:MM local time (AEST)."
    )
    default_duration_minutes = models.PositiveIntegerField(default=60)
    default_block_label = models.CharField(max_length=128, blank=True, null=True)
    last_materialized_until = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"Schedule for {self.sub.stripe_subscription_id} - {self.weekdays_csv} @ {self.default_time}"


class Tag(models.Model):
    """Simple CRM tag."""
    name = models.CharField(max_length=64, unique=True)
    color = models.CharField(max_length=7, blank=True, null=True, help_text="Hex like #2E86AB")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ServiceDefaults(models.Model):
    """
    Lets you declare default duration per service_code, to prefill end time.
    """
    service_code = models.CharField(max_length=64, unique=True)
    duration_minutes = models.PositiveIntegerField(default=60)
    notes = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name_plural = "Service defaults"

    def __str__(self):
        return f"{self.service_code} ({self.duration_minutes}min)"


class TimetableBlock(models.Model):
    """
    Arbitrary daily time blocks you define (no fixed windows).
    e.g., 07:00–10:30 "Morning Run", 11:00–14:00 "Midday", etc.
    """
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    label = models.CharField(max_length=128, blank=True, null=True)

    class Meta:
        ordering = ["date", "start_time"]
        unique_together = ("date", "start_time", "end_time", "label")

    def __str__(self):
        return f"{self.date} {self.start_time}–{self.end_time} {self.label or ''}"


class BlockCapacity(models.Model):
    """
    Capacity per service within a block (you set this in Admin).
    """
    block = models.ForeignKey(TimetableBlock, on_delete=models.CASCADE, related_name="capacities")
    service_code = models.CharField(max_length=64)
    capacity = models.PositiveIntegerField(default=0)
    allow_overlap = models.BooleanField(default=False)  # if this service can overlap with other services in the block

    class Meta:
        unique_together = ("block", "service_code")
        verbose_name_plural = "Block capacities"

    def __str__(self):
        return f"{self.block} - {self.service_code}: {self.capacity}"


class CapacityHold(models.Model):
    """
    Short-lived hold to avoid race conditions during PaymentIntent confirmation.
    """
    token = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    block = models.ForeignKey(TimetableBlock, on_delete=models.CASCADE)
    service_code = models.CharField(max_length=64)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name_plural = "Capacity holds"

    def __str__(self):
        return f"Hold {self.token} for {self.block}"

    @classmethod
    def purge_expired(cls):
        cls.objects.filter(expires_at__lt=timezone.now()).delete()