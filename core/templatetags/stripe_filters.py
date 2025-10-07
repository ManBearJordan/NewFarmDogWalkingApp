"""Template filters for Stripe-related URLs and formatting."""
from django import template

register = template.Library()


@register.filter
def stripe_payment_url(payment_intent_id):
    """
    Generate the correct Stripe Dashboard URL for a PaymentIntent.
    
    Args:
        payment_intent_id: The Stripe PaymentIntent ID (e.g., "pi_test_123")
        
    Returns:
        str: Full URL to the payment in Stripe Dashboard
    """
    if not payment_intent_id:
        return "#"
    
    from core.stripe_integration import payment_intent_dashboard_url
    try:
        return payment_intent_dashboard_url(payment_intent_id)
    except Exception:
        # Fallback to test mode if we can't determine
        return f"https://dashboard.stripe.com/test/payments/{payment_intent_id}"
