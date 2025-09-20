from django.db import models

class StripeSettings(models.Model):
    """Optional admin-surfaceable Stripe key; runtime prefers environment or keyring."""
    stripe_secret_key = models.CharField(max_length=200, blank=True, null=True)
    is_live_mode = models.BooleanField(default=False)

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