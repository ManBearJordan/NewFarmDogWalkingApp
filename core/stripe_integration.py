"""Simplified Stripe integration helper.
Reads Stripe secret from STRIPE_SECRET_KEY env var first, optional keyring fallback.
Exposes get_api_key() and list_active_subscriptions().
"""
import os
import stripe
import time
from typing import List, Dict, Optional, Any, Tuple

from .stripe_key_manager import get_stripe_key

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


def list_booking_services(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Returns active services derived from Stripe Prices + Products.
    Caches results for STRIPE_CATALOG_TTL_SECONDS (default 300s).
    If Stripe key is missing or an API error occurs, returns cached if available, else [].
    """
    if not force_refresh and _cache_valid():
        return list(_CATALOG_CACHE.get("items") or [])
    try:
        items = _fetch_catalog_from_stripe()
        _set_cache(items)
        return items
    except Exception:
        # Fallback to whatever we have
        cached = list(_CATALOG_CACHE.get("items") or [])
        return cached


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


def list_recent_invoices(limit: int = 10) -> List[Dict]:
    """List recent invoices for clients that exist in our database.
    
    Args:
        limit: Maximum number of invoices to return (default 10)
        
    Returns:
        List[Dict]: List of invoice data with keys:
        [{id, client_name, amount_cents, currency, status, created, client_id}, ...]
        Returns empty list if Stripe not configured.
    """
    key = get_api_key()
    if not key:
        # Return stub data if Stripe not configured
        return []
    
    try:
        stripe.api_key = key
        
        # Get recent invoices from Stripe
        invoices = stripe.Invoice.list(
            limit=limit,
            expand=['data.customer']
        )
        
        # Import here to avoid circular imports
        from core.models import Client
        
        # Get all our clients for lookup
        our_clients = {client.stripe_customer_id: client 
                      for client in Client.objects.filter(stripe_customer_id__isnull=False)}
        
        result = []
        for invoice in invoices.data:
            # Only include invoices for clients in our database
            customer_id = invoice.customer.id if hasattr(invoice.customer, 'id') else invoice.customer
            if customer_id in our_clients:
                client = our_clients[customer_id]
                result.append({
                    'id': invoice.id,
                    'client_name': client.name,
                    'client_id': client.id,
                    'amount_cents': invoice.total,
                    'currency': invoice.currency.upper(),
                    'status': invoice.status,
                    'created': invoice.created
                })
        
        return result
        
    except Exception as e:
        # Return empty list on any error to avoid breaking the page
        print(f"Warning: Could not retrieve invoices from Stripe: {e}")
        return []


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


def get_invoice_dashboard_url(invoice_id: str) -> str:
    """Return full dashboard URL for invoice."""
    return open_invoice_smart(invoice_id)


def get_invoice_public_url(invoice_id: str) -> Optional[str]:
    """
    Return the hosted invoice URL (client-facing) or None if not available.
    """
    try:
        _init_stripe()
    except Exception:
        return None
    try:
        inv = stripe.Invoice.retrieve(invoice_id, expand=[])
        return inv.get("hosted_invoice_url")
    except Exception:
        return None


def _dashboard_base() -> str:
    key = get_stripe_key()
    if not key:
        # keep a sane default that won't 404 horribly
        return "https://dashboard.stripe.com"
    return "https://dashboard.stripe.com" if "_live_" in key or key.startswith("sk_live") else "https://dashboard.stripe.com/test"

def get_customer_dashboard_url(customer_id: str) -> str:
    """Return the correct dashboard link for a Stripe customer (test/live aware)."""
    base = _dashboard_base()
    return f"{base}/customers/{customer_id}"


def _init_stripe():
    key = get_stripe_key()
    if not key:
        raise RuntimeError("Stripe key is not configured")
    stripe.api_key = key
    return key


def cancel_subscription_immediately(sub_id: str) -> None:
    """
    Immediately cancel a subscription in Stripe.
    """
    _init_stripe()
    # Prefer delete; if the account forbids hard delete, fall back to update.
    try:
        stripe.Subscription.delete(sub_id)
    except Exception:
        stripe.Subscription.modify(sub_id, cancel_at_period_end=False)
        stripe.Subscription.cancel(sub_id)

# --------------------------------------------------------------------
# Live Service Catalog (Products/Prices) with TTL cache
_CATALOG_CACHE: Dict[str, Any] = {
    "at": 0,            # unix ts
    "items": [],        # cached result list
}

def _catalog_ttl_seconds() -> int:
    # soft dependency on settings to avoid circular imports at import time
    try:
        from django.conf import settings
        return int(getattr(settings, "STRIPE_CATALOG_TTL_SECONDS", 300))
    except Exception:
        return 300

def _now_ts() -> int:
    return int(time.time())

def _cache_valid() -> bool:
    age = _now_ts() - int(_CATALOG_CACHE.get("at") or 0)
    return age < _catalog_ttl_seconds()

def _set_cache(items: List[Dict[str, Any]]) -> None:
    _CATALOG_CACHE["items"] = items or []
    _CATALOG_CACHE["at"] = _now_ts()

def _map_prices_to_services(prices: List[Any]) -> List[Dict[str, Any]]:
    """
    Map Stripe Price objects (with expanded product if available) into the app's catalog schema.
    We prefer:
      - service_code     := product.metadata.service_code OR price.nickname OR product.name (slugified by caller if needed)
      - display_name     := product.name OR price.nickname
      - amount_cents     := price.unit_amount (int)
      - product_id       := product.id
      - price_id         := price.id
    """
    out: List[Dict[str, Any]] = []
    for p in prices:
        prod = p.get("product")
        # When not expanded, prod may be a string id; try to use what we can.
        prod_id = prod.get("id") if isinstance(prod, dict) else (prod if isinstance(prod, str) else None)
        prod_name = (prod.get("name") if isinstance(prod, dict) else None) or ""
        service_code = None
        if isinstance(prod, dict):
            meta = prod.get("metadata") or {}
            service_code = meta.get("service_code")
        # fallback chain for code
        service_code = service_code or (p.get("nickname") or "") or (prod_name or "")
        display_name = prod_name or (p.get("nickname") or "")
        amount_cents = p.get("unit_amount")
        out.append({
            "service_code": service_code,
            "display_name": display_name or service_code or "Service",
            "amount_cents": int(amount_cents) if isinstance(amount_cents, int) else None,
            "product_id": prod_id,
            "price_id": p.get("id"),
        })
    # De-dup by price_id (safety), keep order from Stripe
    seen = set()
    uniq = []
    for item in out:
        pid = item["price_id"]
        if pid in seen:
            continue
        seen.add(pid)
        uniq.append(item)
    return uniq

def _fetch_catalog_from_stripe() -> List[Dict[str, Any]]:
    _init_stripe()
    # Pull active Prices, expand product to avoid extra round trips
    res = stripe.Price.list(active=True, expand=["data.product"], limit=100)
    prices = list(res.auto_paging_iter(limit=100))
    return _map_prices_to_services(prices)

def ensure_customer(client) -> str:
    """
    Ensure a Stripe customer exists for this client, keyed by email when available.
    Updates phone/address on match. Returns stripe_customer_id.
    """
    _init_stripe()
    email = (client.email or "").strip().lower()
    if email:
        # Try to find by email
        res = stripe.Customer.search(query=f'email:"{email}"', limit=1)
        for c in res.auto_paging_iter(limit=1):
            stripe.Customer.modify(c["id"], name=client.name or None, phone=client.phone or None, address=None)
            return c["id"]
    # Create if not found / no email
    created = stripe.Customer.create(
        name=client.name or None,
        email=email or None,
        phone=client.phone or None,
        address=None,
    )
    return created["id"]


def create_payment_intent(amount_cents, customer_id=None, metadata=None):
    """Create a PaymentIntent for portal pre-pay checkout."""
    _init_stripe()
    return stripe.PaymentIntent.create(
        amount=amount_cents,
        currency="aud",
        customer=customer_id,
        metadata=metadata or {},
        automatic_payment_methods={"enabled": True},
    )


def cancel_payment_intent(pi_id):
    """Cancel a PaymentIntent."""
    _init_stripe()
    return stripe.PaymentIntent.cancel(pi_id)


def retrieve_payment_intent(pi_id):
    """Retrieve a PaymentIntent."""
    _init_stripe()
    return stripe.PaymentIntent.retrieve(pi_id)