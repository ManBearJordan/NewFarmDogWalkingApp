"""Simplified Stripe integration helper.
Reads Stripe secret from STRIPE_SECRET_KEY env var first, optional keyring fallback.
Exposes get_api_key() and list_active_subscriptions().
"""
import os
import stripe
from typing import Optional, List, Dict

def get_api_key(env_var_name: str = 'STRIPE_SECRET_KEY') -> Optional[str]:
    key = os.getenv(env_var_name)
    if key:
        return key
    # Optional: fallback to keyring if installed
    try:
        import keyring
        k = keyring.get_password('NewFarmDogWalkingApp', 'stripe_secret_key')
        if k:
            return k
    except Exception:
        pass
    # Optional: fallback to Django model
    try:
        from core.models import StripeSettings
        k = StripeSettings.get_stripe_key()
        if k:
            return k
    except Exception:
        pass
    return None

def list_active_subscriptions(api_key: Optional[str] = None, **params):
    key = api_key or get_api_key()
    if not key:
        raise RuntimeError('Stripe API key not configured. Set STRIPE_SECRET_KEY in env or store via admin.')
    stripe.api_key = key
    return stripe.Subscription.list(**params)


def list_booking_services() -> List[Dict]:
    """Return static list of booking services for catalog.
    
    Returns:
        List[Dict]: Service catalog with format:
        [{service_code, display_name, amount_cents, product_id, price_id}, ...]
    """
    return [
        {
            'service_code': 'WALK_30MIN',
            'display_name': '30 Minute Dog Walk',
            'amount_cents': 2000,  # $20.00
            'product_id': 'prod_walk_30min',
            'price_id': 'price_walk_30min'
        },
        {
            'service_code': 'WALK_1HR',
            'display_name': '1 Hour Dog Walk',
            'amount_cents': 3500,  # $35.00
            'product_id': 'prod_walk_1hr',
            'price_id': 'price_walk_1hr'
        },
        {
            'service_code': 'WALK_2HR',
            'display_name': '2 Hour Dog Walk',
            'amount_cents': 6500,  # $65.00
            'product_id': 'prod_walk_2hr',
            'price_id': 'price_walk_2hr'
        },
        {
            'service_code': 'GROOMING_BASIC',
            'display_name': 'Basic Dog Grooming',
            'amount_cents': 4500,  # $45.00
            'product_id': 'prod_grooming_basic',
            'price_id': 'price_grooming_basic'
        },
        {
            'service_code': 'GROOMING_FULL',
            'display_name': 'Full Service Dog Grooming',
            'amount_cents': 7500,  # $75.00
            'product_id': 'prod_grooming_full',
            'price_id': 'price_grooming_full'
        },
        {
            'service_code': 'SITTING_HALF_DAY',
            'display_name': 'Half Day Pet Sitting',
            'amount_cents': 5000,  # $50.00
            'product_id': 'prod_sitting_half_day',
            'price_id': 'price_sitting_half_day'
        },
        {
            'service_code': 'SITTING_FULL_DAY',
            'display_name': 'Full Day Pet Sitting',
            'amount_cents': 9000,  # $90.00
            'product_id': 'prod_sitting_full_day',
            'price_id': 'price_sitting_full_day'
        },
        {
            'service_code': 'OVERNIGHT_CARE',
            'display_name': 'Overnight Pet Care',
            'amount_cents': 12000,  # $120.00
            'product_id': 'prod_overnight_care',
            'price_id': 'price_overnight_care'
        }
    ]


def ensure_customer(client) -> str:
    """Find or create Stripe customer by email, update client.stripe_customer_id.
    
    Args:
        client: Client model instance
        
    Returns:
        str: Stripe customer ID
    """
    # Import here to avoid circular imports
    from core.models import Client
    
    # If client already has a stripe_customer_id, verify it exists
    if client.stripe_customer_id:
        try:
            key = get_api_key()
            if not key:
                raise RuntimeError('Stripe API key not configured. Set STRIPE_SECRET_KEY in env or store via admin.')
            stripe.api_key = key
            
            customer = stripe.Customer.retrieve(client.stripe_customer_id)
            if customer.deleted:
                # Customer was deleted, need to create a new one
                client.stripe_customer_id = None
            else:
                # Normalize phone/address from Stripe if available
                if customer.phone and customer.phone != client.phone:
                    client.phone = customer.phone
                if customer.address:
                    # Reconstruct address from Stripe address object
                    address_parts = []
                    if customer.address.line1:
                        address_parts.append(customer.address.line1)
                    if customer.address.line2:
                        address_parts.append(customer.address.line2)
                    if customer.address.city:
                        address_parts.append(customer.address.city)
                    if customer.address.state:
                        address_parts.append(customer.address.state)
                    if customer.address.postal_code:
                        address_parts.append(customer.address.postal_code)
                    if customer.address.country:
                        address_parts.append(customer.address.country)
                    
                    if address_parts:
                        normalized_address = ', '.join(address_parts)
                        if normalized_address != client.address:
                            client.address = normalized_address
                
                client.save()
                return client.stripe_customer_id
        except stripe.InvalidRequestError:
            # Customer doesn't exist, need to create new one
            client.stripe_customer_id = None
    
    # Need to create new customer
    if not client.stripe_customer_id:
        key = get_api_key()
        if not key:
            raise RuntimeError('Stripe API key not configured. Set STRIPE_SECRET_KEY in env or store via admin.')
        stripe.api_key = key
        
        # Search for existing customer by email first
        existing_customers = stripe.Customer.list(email=client.email, limit=1)
        if existing_customers.data:
            customer = existing_customers.data[0]
            client.stripe_customer_id = customer.id
            client.save()
            return customer.id
        
        # Create new customer
        customer = stripe.Customer.create(
            email=client.email,
            name=client.name,
            phone=client.phone if client.phone else None,
            metadata={
                'client_id': str(client.id),
                'source': 'NewFarmDogWalkingApp'
            }
        )
        
        client.stripe_customer_id = customer.id
        client.save()
        return customer.id
    
    return client.stripe_customer_id


def create_or_reuse_draft_invoice(client) -> str:
    """Return a draft invoice ID for the client (reuse existing draft if present).
    
    Args:
        client: Client model instance
        
    Returns:
        str: Draft invoice ID
    """
    key = get_api_key()
    if not key:
        raise RuntimeError('Stripe API key not configured. Set STRIPE_SECRET_KEY in env or store via admin.')
    stripe.api_key = key
    
    # Ensure customer exists in Stripe
    customer_id = ensure_customer(client)
    
    # Look for existing draft invoice for this customer
    draft_invoices = stripe.Invoice.list(
        customer=customer_id,
        status='draft',
        limit=1
    )
    
    if draft_invoices.data:
        return draft_invoices.data[0].id
    
    # Create new draft invoice
    invoice = stripe.Invoice.create(
        customer=customer_id,
        auto_advance=False,  # Keep as draft
        metadata={
            'client_id': str(client.id),
            'source': 'NewFarmDogWalkingApp'
        }
    )
    
    return invoice.id


def push_invoice_items_from_booking(booking, invoice_id: str) -> None:
    """Add invoice item from booking to invoice.
    
    Args:
        booking: Booking model instance
        invoice_id: Stripe invoice ID
    """
    key = get_api_key()
    if not key:
        raise RuntimeError('Stripe API key not configured. Set STRIPE_SECRET_KEY in env or store via admin.')
    stripe.api_key = key
    
    # Create invoice item
    stripe.InvoiceItem.create(
        customer=booking.client.stripe_customer_id,
        invoice=invoice_id,
        amount=booking.price_cents,
        currency='usd',
        description=f"{booking.service_name} - {booking.start_dt.strftime('%Y-%m-%d %H:%M')}",
        metadata={
            'booking_id': str(booking.id),
            'service_code': booking.service_code,
            'source': 'NewFarmDogWalkingApp'
        }
    )


def open_invoice_smart(invoice_id: str) -> str:
    """Return full dashboard URL for invoice in test vs live mode.
    
    Args:
        invoice_id: Stripe invoice ID
        
    Returns:
        str: Dashboard URL
    """
    key = get_api_key()
    if not key:
        raise RuntimeError('Stripe API key not configured. Set STRIPE_SECRET_KEY in env or store via admin.')
    
    # Determine if key is test or live mode
    is_test_mode = key.startswith('sk_test_')
    
    if is_test_mode:
        return f"https://dashboard.stripe.com/test/invoices/{invoice_id}"
    else:
        return f"https://dashboard.stripe.com/invoices/{invoice_id}"