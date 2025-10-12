import json, stripe
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseBadRequest
from django.conf import settings
from .stripe_integration import get_stripe_key
from .models import Client, StripeSubscriptionLink
from .stripe_subscriptions import materialize_future_holds, resolve_service_code

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

    return HttpResponse("ok", status=200)
