from __future__ import annotations
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from .models import Booking
from . import subscription_sync

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=10, max_retries=5)
def sync_subscriptions_daily(self):
    """
    Materialize/refresh future subscription occurrences and calendar holds.
    Mirrors the manual 'Troubleshoot Sync' but runs unattended daily when beat is enabled.
    """
    stats = subscription_sync.sync_subscriptions_to_bookings_and_calendar()
    return stats

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5, max_retries=3)
def send_booking_confirmation_email(self, booking_id: int):
    """
    Simple confirmation email after a portal booking succeeds.
    Uses Django's email backend; configure EMAIL_* in settings for production delivery.
    """
    b = Booking.objects.select_related("client").get(id=booking_id)
    to = [b.client.email] if b.client and b.client.email else []
    if not to:
        return "no-recipient"
    subject = "Booking confirmed"
    start = timezone.localtime(b.start_dt).strftime("%a %d %b, %I:%M %p")
    end = timezone.localtime(b.end_dt).strftime("%I:%M %p")
    body = (
        f"Hi {b.client.name},\n\n"
        f"Your booking for {b.service_label or b.service_code} is confirmed.\n"
        f"When: {start} – {end}\n"
        f"Location: {b.location or '—'}\n\n"
        f"Thanks,\nNew Farm Dog Walking"
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@newfarmdogwalking.local"),
        recipient_list=to,
        fail_silently=False,
    )
    return "sent"