"""
Core Django models for the dog walking application.

These models represent the core business logic for subscriptions, bookings,
and schedules. They work alongside the existing SQLite database structure
but use Django ORM for improved maintainability and scalability.
"""

from django.db import models
from django.core.validators import MinValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
import json


class Client(models.Model):
    """
    Represents a client/customer in the system.
    Maps to existing clients table but adds Django ORM benefits.
    """
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    credit_cents = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default='active')
    acquisition_date = models.DateTimeField(default=timezone.now)
    last_service_date = models.DateTimeField(blank=True, null=True)
    total_revenue_cents = models.IntegerField(default=0)
    service_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clients'  # Use existing table name
        managed = True

    def __str__(self):
        return self.name

    @property
    def credit_dollars(self):
        """Return credit amount in dollars"""
        return self.credit_cents / 100

    @property
    def total_revenue_dollars(self):
        """Return total revenue in dollars"""
        return self.total_revenue_cents / 100


class Subscription(models.Model):
    """
    Django model for subscription management.
    
    This model represents a recurring service subscription with schedule information
    that matches Stripe metadata fields. It enables better data management and
    provides a foundation for Django admin and API functionality.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('incomplete', 'Incomplete'),
        ('incomplete_expired', 'Incomplete Expired'),
        ('trialing', 'Trialing'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('unpaid', 'Unpaid'),
    ]

    # Core subscription fields
    stripe_subscription_id = models.CharField(max_length=100, unique=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='subscriptions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Service information
    service_code = models.CharField(max_length=50, help_text="Canonical service code from service_map")
    service_name = models.CharField(max_length=200, help_text="Human readable service name")
    
    # Schedule metadata fields (matching Stripe metadata)
    schedule_days = models.CharField(
        max_length=50,
        help_text="Comma-separated days (MON,TUE,WED,etc.)",
        validators=[RegexValidator(
            regex=r'^([A-Z]{3},)*[A-Z]{3}$',
            message="Days must be comma-separated 3-letter codes (e.g., MON,WED,FRI)"
        )]
    )
    schedule_start_time = models.TimeField(help_text="Start time in HH:MM format")
    schedule_end_time = models.TimeField(help_text="End time in HH:MM format")
    schedule_location = models.CharField(
        max_length=200, 
        blank=True, 
        null=True,
        help_text="Full address where the dog walking service will be provided"
    )
    schedule_dogs = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of dogs to be walked during this service (minimum 1)"
    )
    schedule_notes = models.TextField(
        blank=True, 
        null=True,
        help_text="Additional notes or special instructions for the dog walker"
    )
    
    # Metadata and tracking
    created_from_stripe = models.BooleanField(default=True)
    stripe_created_at = models.DateTimeField(blank=True, null=True)
    last_sync_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stripe_subscription_id']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['service_code']),
        ]

    def __str__(self):
        return f"{self.client.name} - {self.service_name} ({self.stripe_subscription_id})"
    
    def clean(self):
        """Validate subscription data"""
        errors = {}
        
        # Validate time range
        if self.schedule_start_time and self.schedule_end_time:
            if self.schedule_end_time <= self.schedule_start_time:
                errors['schedule_end_time'] = 'End time must be after start time'
        
        # Validate days format
        if self.schedule_days:
            valid_days = {'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'}
            days_list = [day.strip().upper() for day in self.schedule_days.split(',')]
            
            # Check for invalid days
            invalid_days = [day for day in days_list if day not in valid_days]
            if invalid_days:
                errors['schedule_days'] = f'Invalid days: {", ".join(invalid_days)}. Use: MON, TUE, WED, THU, FRI, SAT, SUN'
            
            # Check for duplicates
            if len(days_list) != len(set(days_list)):
                errors['schedule_days'] = 'Duplicate days are not allowed'
        
        # Validate service code is not empty
        if not self.service_code or not self.service_code.strip():
            errors['service_code'] = 'Service code is required'
            
        if errors:
            raise ValidationError(errors)

    @property
    def schedule_days_list(self):
        """Return schedule days as a list"""
        return [day.strip() for day in self.schedule_days.split(',') if day.strip()]

    @property
    def schedule_duration(self):
        """Return schedule duration as timedelta"""
        from datetime import datetime, time
        start = datetime.combine(datetime.today(), self.schedule_start_time)
        end = datetime.combine(datetime.today(), self.schedule_end_time)
        if end < start:
            end += timedelta(days=1)
        return end - start

    def get_next_occurrence(self, from_date=None):
        """Get the next scheduled occurrence from the given date"""
        from datetime import datetime, date
        if from_date is None:
            from_date = timezone.now().date()
        
        days_map = {
            'MON': 0, 'TUE': 1, 'WED': 2, 'THU': 3,
            'FRI': 4, 'SAT': 5, 'SUN': 6
        }
        
        target_weekdays = [days_map[day] for day in self.schedule_days_list if day in days_map]
        
        if not target_weekdays:
            return None
            
        current_date = from_date
        for i in range(14):  # Look ahead 2 weeks max
            if current_date.weekday() in target_weekdays:
                return current_date
            current_date += timedelta(days=1)
        
        return None


class Booking(models.Model):
    """
    Django model for individual bookings.
    
    Represents a single scheduled service appointment. Can be created from
    subscriptions or manually. Provides integration with existing booking
    logic while adding Django ORM benefits.
    """
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled'),
        ('no_show', 'No Show'),
    ]

    SOURCE_CHOICES = [
        ('manual', 'Manual'),
        ('subscription', 'Subscription'),
        ('recurring', 'Recurring'),
    ]

    # Core booking fields
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='bookings')
    subscription = models.ForeignKey(
        Subscription, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='bookings'
    )
    
    # Schedule information
    start_dt = models.DateTimeField(help_text="Start date and time")
    end_dt = models.DateTimeField(help_text="End date and time")
    
    # Service details
    service_type = models.CharField(max_length=50, help_text="Service code")
    service_name = models.CharField(max_length=200, help_text="Human readable service name")
    location = models.CharField(max_length=200, blank=True, null=True)
    dogs = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    notes = models.TextField(blank=True, null=True)
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='manual')
    
    # Stripe integration
    created_from_sub_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Stripe subscription ID if created from subscription"
    )
    stripe_invoice_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_price_id = models.CharField(max_length=100, blank=True, null=True)
    invoice_url = models.URLField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_dt']
        indexes = [
            models.Index(fields=['client', 'start_dt']),
            models.Index(fields=['subscription', 'start_dt']),
            models.Index(fields=['created_from_sub_id', 'start_dt']),
            models.Index(fields=['status']),
            models.Index(fields=['service_type']),
        ]
        # Prevent duplicate bookings from same subscription
        constraints = [
            models.UniqueConstraint(
                fields=['created_from_sub_id', 'start_dt'],
                condition=models.Q(created_from_sub_id__isnull=False),
                name='unique_subscription_booking'
            )
        ]

    def __str__(self):
        return f"{self.client.name} - {self.service_name} on {self.start_dt.date()}"

    @property
    def duration(self):
        """Return booking duration as timedelta"""
        return self.end_dt - self.start_dt

    @property 
    def is_today(self):
        """Check if booking is today"""
        return self.start_dt.date() == timezone.now().date()

    @property
    def is_upcoming(self):
        """Check if booking is in the future"""
        return self.start_dt > timezone.now()

    def can_be_invoiced(self):
        """Check if booking can be invoiced"""
        return self.status in ['completed'] and not self.stripe_invoice_id


class Schedule(models.Model):
    """
    Model for storing schedule templates and patterns.
    
    This can be used for recurring schedules that aren't tied to specific
    subscriptions, or as templates for creating new subscriptions.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    
    # Schedule pattern
    days_of_week = models.CharField(max_length=50)  # JSON string of day numbers
    start_time = models.TimeField()
    end_time = models.TimeField()
    service_code = models.CharField(max_length=50)
    default_location = models.CharField(max_length=200, blank=True, null=True)
    default_dogs = models.IntegerField(default=1)
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def days_list(self):
        """Return days as list of integers"""
        try:
            return json.loads(self.days_of_week)
        except (json.JSONDecodeError, TypeError):
            return []


class StripeSettings(models.Model):
    """
    Model for storing Stripe API configuration via Django admin.
    
    This allows administrators to view and update the Stripe API key 
    through the Django admin interface, making it accessible via web UI
    instead of requiring desktop GUI or command line access.
    """
    stripe_secret_key = models.CharField(
        max_length=200,
        help_text="Stripe Secret Key (sk_test_... or sk_live_...)",
        blank=True,
        null=True
    )
    is_live_mode = models.BooleanField(
        default=False,
        help_text="Automatically determined based on key prefix"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Stripe Settings"
        verbose_name_plural = "Stripe Settings"
        
    def __str__(self):
        if self.stripe_secret_key:
            key_type = "Live" if self.is_live_mode else "Test"
            masked_key = self.stripe_secret_key[:12] + "..." + self.stripe_secret_key[-4:]
            return f"{key_type} Key: {masked_key}"
        return "No Stripe Key Set"
    
    def save(self, *args, **kwargs):
        """Auto-detect live mode based on key prefix"""
        if self.stripe_secret_key:
            self.is_live_mode = self.stripe_secret_key.startswith('sk_live_')
        else:
            self.is_live_mode = False
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate Stripe key format"""
        if self.stripe_secret_key:
            if not (self.stripe_secret_key.startswith('sk_test_') or 
                    self.stripe_secret_key.startswith('sk_live_')):
                raise ValidationError({
                    'stripe_secret_key': 'Stripe secret key must start with sk_test_ or sk_live_'
                })
    
    @classmethod
    def get_stripe_key(cls):
        """Get the current Stripe API key"""
        try:
            settings_obj = cls.objects.first()
            return settings_obj.stripe_secret_key if settings_obj else None
        except Exception:
            return None
    
    @classmethod
    def set_stripe_key(cls, api_key):
        """Set the Stripe API key (creates or updates the single settings record)"""
        try:
            settings_obj, created = cls.objects.get_or_create(defaults={'stripe_secret_key': api_key})
            if not created:
                settings_obj.stripe_secret_key = api_key
                settings_obj.save()
            return True
        except Exception:
            return False
