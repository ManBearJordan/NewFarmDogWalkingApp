"""
Unified booking helper functions to resolve the issues identified in DEBUGGING_REPORT.md

This module provides:
1. Single resolver for Stripe → client (resolve_client_id)
2. Single service-type derivation path (service_type_from_label)
3. Standardized field population for bookings
"""

import sqlite3
import re
from typing import Optional, Tuple


def resolve_client_id(conn: sqlite3.Connection, stripe_customer_id: str) -> Optional[int]:
    """
    Single, unified function to resolve a Stripe customer ID to a local client ID.
    
    This standardizes on clients.stripe_customer_id (deprecating stripeCustomerId everywhere).
    Used by both invoice importer and subscription save/rebuild paths.
    
    Args:
        conn: Database connection
        stripe_customer_id: Stripe customer ID (starts with 'cus_')
    
    Returns:
        client_id if found, None otherwise
    """
    if not stripe_customer_id or not stripe_customer_id.startswith('cus_'):
        return None
    
    cur = conn.cursor()
    
    # Try stripe_customer_id first (preferred column)
    row = cur.execute("""
        SELECT id FROM clients 
        WHERE stripe_customer_id = ?
        LIMIT 1
    """, (stripe_customer_id,)).fetchone()
    
    if row:
        return row["id"]
    
    # Fallback: try stripeCustomerId (legacy column)
    row = cur.execute("""
        SELECT id FROM clients 
        WHERE stripeCustomerId = ?
        LIMIT 1
    """, (stripe_customer_id,)).fetchone()
    
    if row:
        # Migrate to preferred column
        cur.execute("""
            UPDATE clients 
            SET stripe_customer_id = ? 
            WHERE id = ? AND stripe_customer_id IS NULL
        """, (stripe_customer_id, row["id"]))
        conn.commit()
        return row["id"]
    
    return None


def service_type_from_label(name_or_metadata: str) -> str:
    """
    Single, robust service_type derivation that:
    - Normalizes Unicode (– → -, × → x)
    - Strips parentheses/extra punctuation
    - Maps to canonical codes (e.g., DAYCARE_SINGLE, WALK_SHORT, OVERNIGHT_SINGLE)
    
    Used everywhere bookings are created: importer + subscription writer + manual booking UI.
    
    Args:
        name_or_metadata: Service name or metadata string
    
    Returns:
        Canonical service type code
    """
    if not name_or_metadata:
        return "WALK_GENERAL"
    
    # Step 1: Normalize Unicode characters
    label = name_or_metadata
    label = label.replace('–', '-')  # em dash to hyphen
    label = label.replace('—', '-')  # en dash to hyphen
    label = label.replace('×', 'x')  # multiplication sign to x
    label = label.replace('•', '')   # bullet point
    
    # Step 2: Strip parentheses and extra punctuation, normalize case
    label = re.sub(r'[()[\]{}]', '', label)  # Remove brackets/parentheses
    label = re.sub(r'[^\w\s-]', '', label)   # Remove other punctuation except hyphens
    label = label.lower().strip()
    
    # Step 3: Map to canonical codes
    
    # Handle generic/placeholder labels first
    if label in ['subscription', 'service', 'none', '']:
        return "WALK_GENERAL"
    
    # Daycare services
    if 'daycare' in label or 'day care' in label:
        if 'pack' in label:
            return "DAYCARE_PACKS"
        elif 'weekly' in label and 'visit' in label:
            return "DAYCARE_WEEKLY_PER_VISIT"
        elif 'fortnightly' in label and 'visit' in label:
            return "DAYCARE_FORTNIGHTLY_PER_VISIT"
        else:
            return "DAYCARE_SINGLE"
    
    # Walk services
    elif 'walk' in label:
        if 'short' in label:
            if 'pack' in label:
                return "WALK_SHORT_PACKS"
            else:
                return "WALK_SHORT_SINGLE"
        elif 'long' in label:
            if 'pack' in label:
                return "WALK_LONG_PACKS"
            else:
                return "WALK_LONG_SINGLE"
        else:
            return "WALK_GENERAL"
    
    # Home visit services
    elif 'home visit' in label or 'home-visit' in label:
        if '30m' in label or '30 m' in label or 'thirty' in label:
            if '2x' in label or '2 x' in label or 'twice' in label or 'two' in label:
                return "HOME_VISIT_30M_2X_SINGLE"
            else:
                return "HOME_VISIT_30M_SINGLE"
        else:
            return "HOME_VISIT_30M_SINGLE"
    
    # Overnight services
    elif 'overnight' in label or 'over night' in label:
        if 'pack' in label:
            return "OVERNIGHT_PACKS"
        else:
            return "OVERNIGHT_SINGLE"
    
    # Pickup/dropoff services
    elif 'pickup' in label or 'pick up' in label or 'drop off' in label or 'dropoff' in label:
        return "PICKUP_DROPOFF_SINGLE"
    
    # Poop scoop services
    elif 'scoop' in label or 'poop' in label:
        if 'weekly' in label or 'monthly' in label:
            return "SCOOP_WEEKLY_MONTHLY"
        else:
            return "SCOOP_SINGLE"
    
    # Pet sitting services
    elif 'sitting' in label or 'pet sit' in label:
        return "PET_SITTING_SINGLE"
    
    # Grooming services
    elif 'groom' in label or 'bath' in label or 'wash' in label:
        return "GROOMING_SINGLE"
    
    # Default fallback: convert to reasonable code
    # Remove common words and convert to uppercase with underscores
    fallback = re.sub(r'\b(the|and|or|of|in|on|at|to|for|with|by)\b', '', label)
    fallback = re.sub(r'\s+', '_', fallback.strip())
    fallback = re.sub(r'[^a-zA-Z0-9_]', '', fallback)
    fallback = fallback.upper()
    
    # Ensure it's not empty
    if not fallback:
        return "WALK_GENERAL"
    
    return fallback


def get_canonical_service_info(service_input: str, stripe_price_id: str = None) -> Tuple[str, str]:
    """
    Get canonical service information: (service_type, service_label)
    
    Args:
        service_input: Raw service name/label
        stripe_price_id: Optional Stripe price ID for additional context
    
    Returns:
        Tuple of (service_type_code, display_label)
    """
    # Derive service type using unified function
    service_type = service_type_from_label(service_input)
    
    # Create a clean display label
    if service_input and service_input.lower() not in ['subscription', 'service', 'none', '']:
        service_label = service_input.strip()
    else:
        # Generate label from service type
        service_label = friendly_service_label(service_type)
    
    return service_type, service_label


def friendly_service_label(service_code: str) -> str:
    """
    Convert a service_code to a friendly display label
    """
    if not service_code:
        return "Service"
    
    # Map of service codes to friendly labels
    label_map = {
        "WALK_SHORT_SINGLE": "Short Walk",
        "WALK_SHORT_PACKS": "Short Walk (Pack)",
        "WALK_LONG_SINGLE": "Long Walk", 
        "WALK_LONG_PACKS": "Long Walk (Pack)",
        "WALK_GENERAL": "Dog Walk",
        "HOME_VISIT_30M_SINGLE": "Home Visit – 30m (1×/day)",
        "HOME_VISIT_30M_2X_SINGLE": "Home Visit – 30m (2×/day)",
        "DAYCARE_SINGLE": "Doggy Daycare (per day)",
        "DAYCARE_PACKS": "Doggy Daycare (Pack)",
        "DAYCARE_WEEKLY_PER_VISIT": "Daycare (Weekly / per visit)",
        "DAYCARE_FORTNIGHTLY_PER_VISIT": "Daycare (Fortnightly / per visit)",
        "PICKUP_DROPOFF_SINGLE": "Pick up / Drop off",
        "SCOOP_SINGLE": "Poop Scoop – One-time",
        "SCOOP_WEEKLY_MONTHLY": "Poop Scoop – Weekly/Monthly",
        "OVERNIGHT_SINGLE": "Overnight Care",
        "OVERNIGHT_PACKS": "Overnight Care (Pack)",
        "PET_SITTING_SINGLE": "Pet Sitting",
        "GROOMING_SINGLE": "Grooming & Bath",
    }
    
    if service_code in label_map:
        return label_map[service_code]
    
    # Fallback: prettify the code
    return service_code.replace("_", " ").title()


def create_booking_with_unified_fields(conn: sqlite3.Connection, client_id: int, 
                                     service_input: str, start_dt: str, end_dt: str,
                                     location: str = "", dogs: int = 1, price_cents: int = 0,
                                     notes: str = "", stripe_price_id: str = None,
                                     source: str = "manual", created_from_sub_id: str = None) -> int:
    """
    Create a booking with unified field population.
    
    Always sets:
    - service_type (code)
    - service (pretty label derived from the code)  
    - stripe_price_id (when present)
    
    Args:
        conn: Database connection
        client_id: Client ID
        service_input: Raw service name/input
        start_dt: Start datetime ISO string
        end_dt: End datetime ISO string
        location: Location string
        dogs: Number of dogs
        price_cents: Price in cents
        notes: Notes
        stripe_price_id: Stripe price ID if available
        source: Source of booking ('manual', 'subscription', 'invoice')
        created_from_sub_id: Subscription ID if from subscription
    
    Returns:
        booking_id of created booking
    """
    # Get canonical service info
    service_type, service_label = get_canonical_service_info(service_input, stripe_price_id)
    
    cur = conn.cursor()
    
    # Create booking with all unified fields
    cur.execute("""
        INSERT INTO bookings (
            client_id, service_type, service, service_name,
            start_dt, end_dt, start, end,
            location, dogs, dogs_count, price_cents, notes,
            stripe_price_id, source, created_from_sub_id, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled')
    """, (
        client_id, service_type, service_label, service_label,
        start_dt, end_dt, start_dt, end_dt,
        location, dogs, dogs, price_cents, notes,
        stripe_price_id, source, created_from_sub_id
    ))
    
    booking_id = cur.lastrowid
    conn.commit()
    return booking_id


def purge_future_subscription_bookings(conn: sqlite3.Connection, sub_id: str):
    """
    Delete all future bookings where source='subscription' AND created_from_sub_id=<sub> AND start_dt>=today.
    
    Args:
        conn: Database connection
        sub_id: Subscription ID
    """
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM bookings
        WHERE source = 'subscription'
        AND created_from_sub_id = ?
        AND date(start_dt) >= date('now')
    """, (sub_id,))
    conn.commit()
    print(f"Purged {cur.rowcount} future subscription bookings for {sub_id}")


def rebuild_subscription_bookings(conn: sqlite3.Connection, sub_id: str, 
                                days_mask: int, start_time: str, end_time: str,
                                dogs: int, location: str, notes: str, months_ahead: int = 3) -> int:
    """
    Generate the next N months of bookings for a subscription and insert with unified fields.
    
    Args:
        conn: Database connection
        sub_id: Subscription ID
        days_mask: Bitmask for days (Mon=0, Tue=1, etc.)
        start_time: Start time string (HH:MM)
        end_time: End time string (HH:MM)
        dogs: Number of dogs
        location: Location
        notes: Notes
        months_ahead: Number of months to generate (default 3)
    
    Returns:
        Number of bookings created
    """
    from datetime import date, datetime, timedelta, time
    
    # First, resolve the client_id from the subscription
    client_id = None
    service_input = "Dog Walking Service"  # Default
    
    try:
        import stripe
        from secrets_config import get_stripe_key
        stripe.api_key = get_stripe_key()
        
        # Get subscription with expanded data
        subscription = stripe.Subscription.retrieve(sub_id, expand=['customer', 'items.data.price.product'])
        
        # Resolve client
        customer = subscription.customer
        if hasattr(customer, 'id'):
            client_id = resolve_client_id(conn, customer.id)
        
        # Get service info from subscription items
        items = getattr(subscription, "items", None)
        if items and hasattr(items, "data") and items.data:
            item = items.data[0]
            price = getattr(item, "price", None)
            if price and hasattr(price, "metadata") and price.metadata:
                price_metadata = dict(price.metadata)
                service_input = price_metadata.get('service_name') or price.nickname or service_input
            elif price and hasattr(price, "nickname") and price.nickname:
                service_input = price.nickname
            
            # Try product metadata as fallback
            if price and hasattr(price, 'product') and hasattr(price.product, 'metadata'):
                product_metadata = dict(price.product.metadata or {})
                if service_input == "Dog Walking Service":  # Still default
                    service_input = (product_metadata.get('service_name') or 
                                   price.product.name or service_input)
                                   
    except Exception as e:
        print(f"Error getting subscription details: {e}")
        return 0
    
    if not client_id:
        print(f"Could not resolve client for subscription {sub_id}")
        return 0
    
    # Generate bookings for the next N months
    today = date.today()
    end_date = today + timedelta(days=30 * months_ahead)
    
    def parse_time(time_str: str) -> time:
        h, m = map(int, time_str.split(':'))
        return time(h, m)
    
    start_time_obj = parse_time(start_time)
    end_time_obj = parse_time(end_time)
    
    bookings_created = 0
    current_date = today
    
    while current_date <= end_date:
        weekday = current_date.weekday()  # Mon=0, Tue=1, etc.
        
        if days_mask & (1 << weekday):  # Check if this day is scheduled
            start_dt = datetime.combine(current_date, start_time_obj)
            end_dt = datetime.combine(current_date, end_time_obj)
            
            # Handle overnight services
            if "overnight" in service_input.lower():
                end_dt += timedelta(days=1)
            
            start_dt_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
            end_dt_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")
            
            # Check for existing booking to avoid duplicates
            cur = conn.cursor()
            existing = cur.execute("""
                SELECT id FROM bookings 
                WHERE client_id = ? AND start_dt = ? AND COALESCE(deleted, 0) = 0
            """, (client_id, start_dt_str)).fetchone()
            
            if not existing:
                booking_notes = f"Auto-generated from subscription {sub_id}. {notes}".strip()
                
                booking_id = create_booking_with_unified_fields(
                    conn, client_id, service_input, start_dt_str, end_dt_str,
                    location, dogs, 0, booking_notes, None, 'subscription', sub_id
                )
                bookings_created += 1
        
        current_date += timedelta(days=1)
    
    return bookings_created
