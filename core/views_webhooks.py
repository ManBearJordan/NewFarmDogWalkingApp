import json, stripe, logging
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseBadRequest
from django.conf import settings
from django.utils import timezone
from .stripe_integration import get_stripe_key
from .models import Client, StripeSubscriptionLink, Booking, Service, AdminEvent
from .stripe_subscriptions import materialize_future_holds, resolve_service_code

logger = logging.getLogger(__name__)

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig = request.META.get("HTTP_STRIPE_SIGNATURE")
    secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)
    stripe.api_key = get_stripe_key()
    try:
        if secret:
            event = stripe.Webhook.construct_event(payload=payload, sig_header=sig, secret=secret)
        else:
            event = json.loads(payload)
    except Exception:
        return HttpResponseBadRequest("Invalid signature/payload")

    t = event.get("type")
    data = event.get("data", {}).get("object", {})

    if t in ("customer.subscription.created", "customer.subscription.updated"):
        sub_id = data.get("id")
        cust = data.get("customer")
        status = data.get("status")
        # Find client by customer
        try:
            client = Client.objects.get(stripe_customer_id=cust)
        except Client.DoesNotExist:
            return HttpResponse("No matching client", status=200)
        # Guess service_code from price/product nickname
        price = (data.get("items", {}).get("data", [{}])[0]).get("price", {})
        nickname = price.get("nickname") or ""
        service_code = resolve_service_code(nickname) or "walk"
        
        # Log if service_code doesn't exist in database
        if service_code and not Service.objects.filter(code=service_code).exists():
            logger.warning(f"Subscription {sub_id}: Unknown service_code from nickname → {service_code} (nickname: {nickname})")
        
        link, _ = StripeSubscriptionLink.objects.update_or_create(
            stripe_subscription_id=sub_id,
            defaults={"client": client, "service_code": service_code, "status": status},
        )
        # If already scheduled, refresh future holds
        try:
            materialize_future_holds(link, horizon_days=30)
        except Exception:
            pass

    if t == "customer.subscription.deleted":
        sub_id = data.get("id")
        StripeSubscriptionLink.objects.filter(stripe_subscription_id=sub_id).update(status="canceled")

    # --- Invoice events ---
    if t.startswith("invoice."):
        inv = data
        invoice_id = inv.get('id')
        hosted_pdf = None
        # Try to extract a useful URL for the invoice PDF or hosted invoice
        try:
            hosted_pdf = inv.get('invoice_pdf') or inv.get('hosted_invoice_url') or None
        except Exception:
            hosted_pdf = None

        # Extract and validate metadata
        metadata = inv.get('metadata', {})
        booking_id = metadata.get('booking_id')
        service_code = metadata.get('service_code')
        
        # Log missing or invalid booking_id
        if not booking_id or not Booking.objects.filter(id=booking_id).exists():
            logger.warning(f"Invoice {invoice_id}: Invalid or missing booking_id in metadata → {booking_id}")
            # Log to AdminEvent if metadata appears malformed
            if metadata and not booking_id:
                AdminEvent.log("stripe_metadata_error", f"Invoice {invoice_id} has malformed metadata: {dict(metadata)}")
        
        # Log invalid service_code (if present)
        if service_code and not Service.objects.filter(code=service_code).exists():
            logger.warning(f"Invoice {invoice_id}: Unknown service_code from metadata → {service_code}")
        
        # Check for unexpected metadata keys (debug mode only)
        if settings.STRIPE_METADATA_LOGGING and metadata:
            known_keys = {"booking_id", "service_code", "date", "time"}
            unknown_keys = set(metadata.keys()) - known_keys
            if unknown_keys:
                logger.debug(f"Invoice {invoice_id}: Unused metadata fields → {sorted(unknown_keys)}")

        if invoice_id:
            qs = Booking.objects.filter(stripe_invoice_id=invoice_id)
            if qs.exists():
                for b in qs:
                    if t == "invoice.finalized":
                        # Just attach URL; status still unpaid until payment succeeds
                        if hosted_pdf and b.invoice_pdf_url != hosted_pdf:
                            b.invoice_pdf_url = hosted_pdf
                            b.save(update_fields=["invoice_pdf_url"])
                    elif t == "invoice.payment_succeeded":
                        if hosted_pdf and b.invoice_pdf_url != hosted_pdf:
                            b.invoice_pdf_url = hosted_pdf
                        b.payment_status = 'paid'
                        if b.paid_at is None:
                            b.paid_at = timezone.now()
                        b.save(update_fields=["invoice_pdf_url", "payment_status", "paid_at"])
                    elif t == "invoice.voided":
                        b.payment_status = 'void'
                        b.save(update_fields=["payment_status"])
                    elif t == "invoice.payment_failed":
                        b.payment_status = 'failed'
                        b.save(update_fields=["payment_status"])
        return HttpResponse("ok")

    return HttpResponse("ok", status=200)
