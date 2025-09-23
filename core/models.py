from django.db import models
from django.conf import settings


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
    email = models.EmailField()
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

    def __str__(self):
        return self.name


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
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    service_code = models.CharField(max_length=50)
    service_name = models.CharField(max_length=200)
    service_label = models.CharField(max_length=200)
    start_dt = models.DateTimeField()
    end_dt = models.DateTimeField()
    location = models.CharField(max_length=200)
    dogs = models.IntegerField(default=1)
    status = models.CharField(max_length=50)
    price_cents = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    stripe_invoice_id = models.CharField(max_length=200, blank=True, null=True)
    deleted = models.BooleanField(default=False)

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


class SubOccurrence(models.Model):
    stripe_subscription_id = models.CharField(max_length=200)
    start_dt = models.DateTimeField()
    end_dt = models.DateTimeField()
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"Sub {self.stripe_subscription_id} ({self.start_dt.date()} - {self.end_dt.date()})"


class Tag(models.Model):
    """Simple CRM tag."""
    name = models.CharField(max_length=64, unique=True)
    color = models.CharField(max_length=7, blank=True, null=True, help_text="Hex like #2E86AB")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name