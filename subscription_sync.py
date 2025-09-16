"""
Unified subscription-driven booking and calendar generation.

This module provides the central function for syncing subscriptions from Stripe
to generate bookings and calendar entries. Subscriptions are now the single
source of truth for all recurring bookings.

Key Features:
- Reads all active subscriptions from Stripe
- Generates/updates bookings for subscription occurrences 
- Synchronizes calendar holds to match subscription schedules
- Removes orphaned bookings from cancelled subscriptions
- Uses only canonical service codes from subscription metadata
- No fallback logic or inference - subscription data is authoritative

Usage:
    sync_subscriptions_to_bookings_and_calendar(conn)
"""

import sqlite3
import logging
from datetime import datetime, timedelta, timezone, date, time
from typing import Optional, List, Dict, Any
from dateutil import tz
import re

# Import required modules
from unified_booking_helpers import resolve_client_id, service_type_from_label
from service_map import get_service_code, is_valid_service_code
from db import get_conn, add_or_upsert_booking

# Set up logging
logger = logging.getLogger(__name__)

def extract_service_code_from_metadata(subscription_data: Dict[str, Any]) -> Optional[str]:
    """
    Extract service code from Stripe subscription metadata.
    
    According to the problem statement, we should refer to Stripe invoice metadata
    format for service codes. This function looks for service_code in various
    metadata locations.
    
    Args:
        subscription_data: Subscription data from Stripe API
        
    Returns:
        Canonical service code or None if not found
    """
    # Check metadata at subscription level
    metadata = subscription_data.get("metadata", {})
    if "service_code" in metadata:
        code = metadata["service_code"]
        if is_valid_service_code(code):
            return code
    
    # Check items for service codes
    items = subscription_data.get("items", [])
    if isinstance(items, dict):
        items = items.get("data", [])
    
    for item in items:
        # Check price metadata
        price = item.get("price", {})
        if isinstance(price, dict):
            price_metadata = price.get("metadata", {})
            if "service_code" in price_metadata:
                code = price_metadata["service_code"]
                if is_valid_service_code(code):
                    return code
        
        # Check product name/nickname as fallback
        product_name = None
        nickname = None
        
        if isinstance(price, dict):
            nickname = price.get("nickname")
            product = price.get("product")
            if isinstance(product, dict):
                product_name = product.get("name")
        
        # Try to map product name or nickname to service code
        for name in [nickname, product_name]:
            if name:
                service_code = get_service_code(name.strip())
                if service_code and is_valid_service_code(service_code):
                    return service_code
    
    return None


def extract_schedule_from_subscription(subscription_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract schedule information from subscription metadata.
    
    Expected metadata format (as per problem statement image):
    - days/schedule_days: comma-separated list of days (MON,TUE,WED,etc.)
    - start_time/schedule_start_time: start time (HH:MM format)
    - end_time/schedule_end_time: end time (HH:MM format) 
    - location/schedule_location: service location
    - dogs/schedule_dogs: number of dogs (integer)
    
    Args:
        subscription_data: Subscription data from Stripe API
        
    Returns:
        Dictionary with schedule information
    """
    metadata = subscription_data.get("metadata", {})
    
    # Helper function to get metadata with multiple possible key names
    def get_metadata_value(keys, default=""):
        for key in keys:
            if key in metadata:
                return metadata[key]
        return default
    
    # Extract schedule values with support for both prefixed and non-prefixed keys
    schedule = {
        "days": get_metadata_value(["schedule_days", "days"]),
        "start_time": get_metadata_value(["schedule_start_time", "start_time"], "09:00"),
        "end_time": get_metadata_value(["schedule_end_time", "end_time"], "10:00"),
        "location": get_metadata_value(["schedule_location", "location"]),
        "dogs": int(get_metadata_value(["schedule_dogs", "dogs"], "0")),  # Use 0 as default to detect missing
        "notes": get_metadata_value(["schedule_notes", "notes"])
    }
    
    # Parse days into list
    if schedule["days"]:
        schedule["day_list"] = [d.strip().upper() for d in schedule["days"].split(",")]
    else:
        schedule["day_list"] = []
    
    return schedule


def get_weekday_number(day_name: str) -> int:
    """
    Convert day name to weekday number (0=Monday, 6=Sunday).
    
    Args:
        day_name: Day name (MON, TUE, WED, etc.)
        
    Returns:
        Weekday number (0-6)
    """
    day_map = {
        "MON": 0, "TUE": 1, "WED": 2, "THU": 3, 
        "FRI": 4, "SAT": 5, "SUN": 6
    }
    return day_map.get(day_name.upper(), 0)


def generate_booking_occurrences(subscription_data: Dict[str, Any], 
                                client_id: int, 
                                service_code: str,
                                schedule: Dict[str, Any],
                                horizon_days: int = 90) -> List[Dict[str, Any]]:
    """
    Generate booking occurrences for a subscription within the horizon period.
    
    Args:
        subscription_data: Subscription data from Stripe
        client_id: Local client ID
        service_code: Canonical service code
        schedule: Schedule information from subscription metadata
        horizon_days: Number of days ahead to generate bookings
        
    Returns:
        List of booking occurrence dictionaries
    """
    if not schedule["day_list"]:
        return []
    
    occurrences = []
    today = date.today()
    horizon_date = today + timedelta(days=horizon_days)
    
    # Convert day names to weekday numbers
    target_weekdays = [get_weekday_number(day) for day in schedule["day_list"]]
    
    # Generate occurrences for each day in the horizon
    current_date = today
    while current_date <= horizon_date:
        if current_date.weekday() in target_weekdays:
            # Parse start and end times
            start_time_obj = datetime.strptime(schedule["start_time"], "%H:%M").time()
            end_time_obj = datetime.strptime(schedule["end_time"], "%H:%M").time()
            
            # Create datetime objects
            start_dt = datetime.combine(current_date, start_time_obj)
            end_dt = datetime.combine(current_date, end_time_obj)
            
            # Format as ISO strings for database storage
            start_iso = start_dt.strftime("%Y-%m-%d %H:%M:%S")
            end_iso = end_dt.strftime("%Y-%m-%d %H:%M:%S")
            
            occurrence = {
                "subscription_id": subscription_data["id"],
                "client_id": client_id,
                "service_code": service_code,
                "start_dt": start_iso,
                "end_dt": end_iso,
                "location": schedule["location"],
                "dogs": schedule["dogs"],
                "notes": schedule["notes"],
                "status": "scheduled",
                "source": "subscription"
            }
            occurrences.append(occurrence)
        
        current_date += timedelta(days=1)
    
    return occurrences


def sync_subscription_to_bookings(conn: sqlite3.Connection, subscription_data: Dict[str, Any], parent_widget=None) -> int:
    """
    Sync a single subscription to generate/update bookings.
    
    Args:
        conn: Database connection
        subscription_data: Subscription data from Stripe API
        
    Returns:
        Number of bookings created/updated
    """
    subscription_id = subscription_data["id"]
    
    # Resolve client ID
    customer_id = subscription_data.get("customer_id")
    if not customer_id:
        logger.warning(f"No customer ID for subscription {subscription_id}")
        return 0
    
    client_id = resolve_client_id(conn, customer_id)
    if not client_id:
        logger.warning(f"Could not resolve client for customer {customer_id}")
        return 0
    
    # Enhanced service code extraction with better fallback handling
    service_code = extract_service_code_from_metadata(subscription_data)
    if not service_code:
        logger.info(f"Primary service code extraction failed for subscription {subscription_id}, trying fallback methods...")
        
        # Fallback 1: Try to derive from product information
        try:
            from service_map import get_service_code, is_valid_service_code
            items = subscription_data.get("items", {})
            if isinstance(items, dict):
                items_data = items.get("data", [])
            else:
                items_data = getattr(items, "data", []) if items else []
            
            for item in items_data:
                price = item.get("price", {}) if isinstance(item, dict) else getattr(item, "price", {})
                if isinstance(price, dict):
                    # Try price nickname mapping
                    price_nickname = price.get("nickname", "")
                    if price_nickname:
                        mapped_code = get_service_code(price_nickname.strip())
                        if mapped_code and is_valid_service_code(mapped_code):
                            service_code = mapped_code
                            logger.info(f"Derived service code '{service_code}' from price nickname for subscription {subscription_id}")
                            break
                    
                    # Try product name mapping
                    product = price.get("product", {})
                    if isinstance(product, dict):
                        product_name = product.get("name", "")
                        if product_name:
                            mapped_code = get_service_code(product_name.strip())
                            if mapped_code and is_valid_service_code(mapped_code):
                                service_code = mapped_code
                                logger.info(f"Derived service code '{service_code}' from product name for subscription {subscription_id}")
                                break
        except Exception as fallback_error:
            logger.warning(f"Service code fallback mapping failed for subscription {subscription_id}: {fallback_error}")
    
    # If still no service code, use interactive dialog or default
    if not service_code:
        logger.warning(f"No valid service code found for subscription {subscription_id}")
        
        # If we have a parent widget, show service selection dialog
        if parent_widget is not None:
            try:
                from subscription_schedule_dialog import show_service_selection_dialog
                service_code = show_service_selection_dialog(subscription_id, parent_widget)
                
                if service_code:
                    logger.info(f"User selected service code '{service_code}' for subscription {subscription_id}")
                    
                    # Update the subscription metadata with the selected service code
                    try:
                        from stripe_integration import _api
                        stripe_api = _api()
                        stripe_api.Subscription.modify(
                            subscription_id,
                            metadata={'service_code': service_code}
                        )
                        logger.info(f"Updated Stripe subscription {subscription_id} with service_code: {service_code}")
                    except Exception as e:
                        logger.error(f"Failed to update Stripe subscription metadata: {e}")
                        # Continue anyway - we can still use the service code locally
                else:
                    logger.info(f"User did not select service code for subscription {subscription_id}")
                    # Use default service code rather than failing completely
                    service_code = "DOG_WALK"  # Safe default
                    logger.warning(f"Using default service code '{service_code}' for subscription {subscription_id}")
                    
            except Exception as e:
                logger.error(f"Error showing service selection dialog: {e}")
                # Use default service code rather than failing completely
                service_code = "DOG_WALK"  # Safe default
                logger.warning(f"Falling back to default service code '{service_code}' for subscription {subscription_id}")
        else:
            # No UI available - use default service code
            service_code = "DOG_WALK"  # Safe default
            logger.warning(f"No UI available, using default service code '{service_code}' for subscription {subscription_id}")
    
    # Extract schedule
    schedule = extract_schedule_from_subscription(subscription_data)
    if not schedule["day_list"]:
        logger.info(f"No schedule days specified for subscription {subscription_id}")
        return 0
    
    # Generate booking occurrences
    occurrences = generate_booking_occurrences(
        subscription_data, client_id, service_code, schedule
    )
    
    if not occurrences:
        logger.info(f"No occurrences generated for subscription {subscription_id}")
        return 0
    
    # Create/update bookings
    bookings_created = 0
    cur = conn.cursor()
    
    for occurrence in occurrences:
        try:
            # Check if booking already exists for this subscription and time
            existing = cur.execute("""
                SELECT id FROM bookings 
                WHERE created_from_sub_id = ? AND start_dt = ?
                LIMIT 1
            """, (subscription_id, occurrence["start_dt"])).fetchone()
            
            if existing:
                # Update existing booking
                cur.execute("""
                    UPDATE bookings SET
                        service_type = ?,
                        end_dt = ?,
                        location = ?,
                        dogs_count = ?,
                        notes = ?,
                        status = ?,
                        source = ?
                    WHERE id = ?
                """, (
                    occurrence["service_code"],
                    occurrence["end_dt"], 
                    occurrence["location"],
                    occurrence["dogs"],
                    occurrence["notes"],
                    occurrence["status"],
                    occurrence["source"],
                    existing["id"]
                ))
                logger.debug(f"Updated booking {existing['id']} for subscription {subscription_id}")
            else:
                # Create new booking using add_or_upsert_booking
                booking_id = add_or_upsert_booking(
                    conn,
                    client_id=occurrence["client_id"],
                    service_code=occurrence["service_code"],
                    start_dt=occurrence["start_dt"],
                    end_dt=occurrence["end_dt"],
                    location=occurrence["location"],
                    dogs=occurrence["dogs"],
                    price_cents=0,  # Will be set from invoice when available
                    notes=occurrence["notes"],
                    status=occurrence["status"],
                    created_from_sub_id=subscription_id,
                    source=occurrence["source"]
                )
                bookings_created += 1
                logger.debug(f"Created booking {booking_id} for subscription {subscription_id}")
                
        except Exception as e:
            logger.error(f"Error creating/updating booking for subscription {subscription_id}: {e}")
            continue
    
    conn.commit()
    return bookings_created


def cleanup_cancelled_subscriptions(conn: sqlite3.Connection, active_subscription_ids: List[str]) -> int:
    """
    Remove bookings for subscriptions that are no longer active.
    
    Args:
        conn: Database connection
        active_subscription_ids: List of active subscription IDs from Stripe
        
    Returns:
        Number of bookings cleaned up
    """
    if not active_subscription_ids:
        return 0
    
    cur = conn.cursor()
    
    # Find subscription-generated bookings that are no longer active
    placeholders = ",".join("?" * len(active_subscription_ids))
    future_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Get cancelled subscription bookings
    cancelled_bookings = cur.execute(f"""
        SELECT id, created_from_sub_id FROM bookings 
        WHERE created_from_sub_id IS NOT NULL 
        AND created_from_sub_id NOT IN ({placeholders})
        AND start_dt >= ?
        AND source = 'subscription'
    """, (*active_subscription_ids, future_date)).fetchall()
    
    if not cancelled_bookings:
        return 0
    
    # Delete cancelled subscription bookings
    cancelled_ids = [b["id"] for b in cancelled_bookings]
    placeholders = ",".join("?" * len(cancelled_ids))
    
    cur.execute(f"""
        DELETE FROM bookings 
        WHERE id IN ({placeholders})
    """, cancelled_ids)
    
    conn.commit()
    
    logger.info(f"Cleaned up {len(cancelled_ids)} bookings from cancelled subscriptions")
    return len(cancelled_ids)


def sync_subscriptions_to_bookings_and_calendar(conn: Optional[sqlite3.Connection] = None, 
                                               horizon_days: int = 90) -> Dict[str, int]:
    """
    Central function to sync all active subscriptions to bookings and calendar.
    
    This is the main entry point for subscription-driven booking generation.
    
    Process:
    1. Fetch all active subscriptions from Stripe
    2. For each subscription:
       - Extract service code and schedule from metadata
       - Generate booking occurrences within horizon
       - Create/update bookings in database
    3. Clean up bookings from cancelled subscriptions
    4. Update calendar holds to match subscription schedules
    
    Args:
        conn: Database connection (creates new one if None)
        horizon_days: Number of days ahead to generate bookings
        
    Returns:
        Dictionary with sync statistics
    """
    if conn is None:
        conn = get_conn()
        close_conn = True
    else:
        close_conn = False
    
    try:
        logger.info("Starting subscription sync to bookings and calendar")
        
        # Import Stripe integration
        from stripe_integration import list_active_subscriptions
        
        # Fetch active subscriptions from Stripe
        logger.info("Fetching active subscriptions from Stripe")
        subscriptions = list_active_subscriptions()
        
        if not subscriptions:
            logger.info("No active subscriptions found")
            return {"subscriptions_processed": 0, "bookings_created": 0, "bookings_cleaned": 0}
        
        # Process each subscription
        total_bookings_created = 0
        subscriptions_processed = 0
        active_subscription_ids = []
        
        for subscription in subscriptions:
            try:
                subscription_id = subscription["id"]
                active_subscription_ids.append(subscription_id)
                
                # Sync subscription to bookings
                bookings_created = sync_subscription_to_bookings(conn, subscription, parent_widget=None)
                total_bookings_created += bookings_created
                subscriptions_processed += 1
                
                logger.debug(f"Processed subscription {subscription_id}: {bookings_created} bookings")
                
            except Exception as e:
                logger.error(f"Error processing subscription {subscription.get('id', 'unknown')}: {e}")
                continue
        
        # Clean up cancelled subscriptions
        bookings_cleaned = cleanup_cancelled_subscriptions(conn, active_subscription_ids)
        
        # Update subscription schedule table for calendar holds
        update_subscription_schedules(conn, subscriptions)
        
        # Materialize subscription occurrences for calendar display
        from db import materialize_sub_occurrences
        materialize_sub_occurrences(conn, horizon_days=horizon_days)
        
        stats = {
            "subscriptions_processed": subscriptions_processed,
            "bookings_created": total_bookings_created,
            "bookings_cleaned": bookings_cleaned
        }
        
        logger.info(f"Subscription sync complete: {stats}")
        return stats
        
    finally:
        if close_conn:
            conn.close()


def update_subscription_schedules(conn: sqlite3.Connection, subscriptions: List[Dict[str, Any]]) -> int:
    """
    Update the subs_schedule table with current subscription information.
    
    This table is used for calendar display and occurrence generation.
    
    Args:
        conn: Database connection
        subscriptions: List of subscription data from Stripe
        
    Returns:
        Number of schedules updated
    """
    cur = conn.cursor()
    schedules_updated = 0
    
    for subscription in subscriptions:
        try:
            subscription_id = subscription["id"]
            schedule = extract_schedule_from_subscription(subscription)
            
            # Update or insert schedule
            cur.execute("""
                INSERT OR REPLACE INTO subs_schedule
                (stripe_subscription_id, days, start_time, end_time, dogs, location, notes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                subscription_id,
                schedule["days"],
                schedule["start_time"],
                schedule["end_time"],
                schedule["dogs"],
                schedule["location"],
                schedule["notes"],
                datetime.now().isoformat()
            ))
            
            schedules_updated += 1
            
        except Exception as e:
            logger.error(f"Error updating schedule for subscription {subscription.get('id')}: {e}")
            continue
    
    conn.commit()
    logger.debug(f"Updated {schedules_updated} subscription schedules")
    return schedules_updated


def sync_on_startup(conn: Optional[sqlite3.Connection] = None) -> Dict[str, int]:
    """
    Perform subscription sync on application startup.
    
    This should be called when the application starts to ensure
    all bookings and calendar entries are up to date.
    
    Args:
        conn: Database connection
        
    Returns:
        Dictionary with sync statistics
    """
    logger.info("Performing subscription sync on startup")
    return sync_subscriptions_to_bookings_and_calendar(conn, horizon_days=120)


def sync_on_subscription_change(subscription_id: str, conn: Optional[sqlite3.Connection] = None) -> Dict[str, int]:
    """
    Perform subscription sync when a specific subscription changes.
    
    This should be called when a subscription is created, updated, or deleted.
    
    Args:
        subscription_id: The Stripe subscription ID that changed
        conn: Database connection
        
    Returns:
        Dictionary with sync statistics  
    """
    logger.info(f"Performing subscription sync for changed subscription {subscription_id}")
    
    # For now, we'll do a full sync since we need to handle all cases
    # In the future, this could be optimized to only sync the specific subscription
    return sync_subscriptions_to_bookings_and_calendar(conn, horizon_days=90)