"""
Subscription validation and missing data detection for the unified subscription workflow.

This module provides functions to validate subscriptions and identify which ones
are missing required schedule information (days, time, location, dog count).
"""

import sqlite3
from typing import List, Dict, Any, Optional
from subscription_sync import extract_schedule_from_subscription, extract_service_code_from_metadata
import logging

logger = logging.getLogger(__name__)

def get_subscriptions_missing_schedule_data(subscriptions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Identify subscriptions that are missing required schedule information.
    
    A subscription is considered to be missing schedule data if any of the following
    are missing or empty:
    - days: No days specified for the schedule
    - start_time/end_time: Missing or invalid time information
    - location: Empty location field
    - dogs: Missing or invalid dog count
    
    Args:
        subscriptions: List of subscription data from Stripe API
        
    Returns:
        List of subscriptions that are missing required schedule data
    """
    missing_data_subscriptions = []
    
    for subscription in subscriptions:
        subscription_id = subscription.get("id")
        if not subscription_id:
            continue
            
        # Extract schedule information 
        schedule = extract_schedule_from_subscription(subscription)
        
        # Check if any required fields are missing or empty
        missing_fields = []
        
        # Extract and check service code - be more permissive for existing subscriptions
        # Only flag as missing if there's genuinely no service code information at all
        metadata = subscription.get("metadata", {})
        has_service_code = (
            metadata.get("service_code") or 
            extract_service_code_from_metadata(subscription)
        )
        
        # Only add service_code as missing if we truly have no service information
        # This prevents blocking workflow for valid subscriptions
        if not has_service_code:
            # Check if we can derive service code from product information
            try:
                from service_map import get_service_code, is_valid_service_code
                items = subscription.get("items", {})
                if isinstance(items, dict):
                    items_data = items.get("data", [])
                else:
                    items_data = getattr(items, "data", []) if items else []
                
                found_mappable_service = False
                for item in items_data:
                    price = item.get("price", {}) if isinstance(item, dict) else getattr(item, "price", {})
                    if isinstance(price, dict):
                        product = price.get("product", {})
                        if isinstance(product, dict):
                            product_name = product.get("name", "")
                            if product_name:
                                mapped_code = get_service_code(product_name.strip())
                                if mapped_code and is_valid_service_code(mapped_code):
                                    found_mappable_service = True
                                    break
                
                # Only flag as missing if we can't map from product either
                if not found_mappable_service:
                    missing_fields.append("service_code")
            except Exception:
                # If service mapping fails, we'll prompt user later rather than blocking
                missing_fields.append("service_code")
        
        # Check days
        if not schedule.get("day_list") or len(schedule["day_list"]) == 0:
            missing_fields.append("days")
            
        # Check times - validate they're not the default values and are reasonable
        start_time = schedule.get("start_time", "")
        end_time = schedule.get("end_time", "")
        if not start_time or start_time == "09:00":  # Default time suggests not set
            missing_fields.append("start_time")
        if not end_time or end_time == "10:00":    # Default time suggests not set
            missing_fields.append("end_time")
            
        # Check location
        location = schedule.get("location", "").strip()
        if not location:
            missing_fields.append("location")
            
        # Check dogs count
        dogs = schedule.get("dogs", 0)
        if not dogs or dogs <= 0:
            missing_fields.append("dogs")
        
        # If any fields are missing, add to the list
        if missing_fields:
            subscription_copy = subscription.copy()
            subscription_copy["missing_fields"] = missing_fields
            subscription_copy["schedule"] = schedule
            missing_data_subscriptions.append(subscription_copy)
            
            logger.debug(f"Subscription {subscription_id} missing fields: {missing_fields}")
    
    return missing_data_subscriptions


def is_subscription_schedule_complete(subscription: Dict[str, Any]) -> bool:
    """
    Check if a subscription has complete schedule information.
    
    This function ensures that a subscription won't trigger dialogs repeatedly
    by being more rigorous about what constitutes "complete" data.
    
    Args:
        subscription: Subscription data from Stripe API
        
    Returns:
        True if schedule is complete, False otherwise
    """
    schedule = extract_schedule_from_subscription(subscription)
    
    # Check for service code but be more permissive - accept any non-empty service code
    metadata = subscription.get("metadata", {})
    has_any_service_code = (
        metadata.get("service_code") or 
        extract_service_code_from_metadata(subscription)
    )
    
    # More rigorous validation to prevent dialogs reappearing
    # Check that all essential fields are present and valid
    
    # Days must be specified and valid
    day_list = schedule.get("day_list", [])
    if not day_list or len(day_list) == 0:
        return False
    
    # Times must be set to meaningful values (not defaults)
    start_time = schedule.get("start_time", "")
    end_time = schedule.get("end_time", "")
    
    # Consider schedule incomplete if using obvious default values
    if (start_time in ("", "09:00") or 
        end_time in ("", "10:00") or
        start_time == end_time):
        return False
    
    # Location must be specified
    location = schedule.get("location", "").strip()
    if not location:
        return False
    
    # Dogs must be a positive number
    dogs = schedule.get("dogs", 0)
    if dogs <= 0:
        return False
    
    # Check if data is actually persisted in local database
    # This prevents the dialog from reappearing after user saves data
    try:
        from db import get_conn
        conn = get_conn()
        cur = conn.cursor()
        
        # Check if this subscription has persistent schedule data
        existing_schedule = cur.execute("""
            SELECT days, start_time, end_time, location, dogs 
            FROM subs_schedule 
            WHERE stripe_subscription_id = ?
        """, (subscription.get("id"),)).fetchone()
        
        if existing_schedule:
            # If we have local data, validate it matches what we expect
            persisted_complete = (
                existing_schedule[0] and  # days
                existing_schedule[1] not in ("", "09:00") and  # start_time
                existing_schedule[2] not in ("", "10:00") and  # end_time
                existing_schedule[3] and existing_schedule[3].strip() != "" and  # location
                existing_schedule[4] and existing_schedule[4] > 0  # dogs
            )
            
            if persisted_complete:
                logger.debug(f"Schedule for subscription {subscription.get('id')} is complete in local database")
                return True
        
        conn.close()
        
    except Exception as e:
        logger.warning(f"Could not check local database for subscription schedule: {e}")
    
    # All validation passed
    return True


def update_stripe_subscription_metadata(subscription_id: str, 
                                       days: str,
                                       start_time: str, 
                                       end_time: str,
                                       location: str,
                                       dogs: int,
                                       notes: str = "",
                                       service_code: str = "") -> bool:
    """
    Update Stripe subscription metadata with schedule information.
    
    This ensures future syncs will have consistent data and won't
    require the modal popup again.
    
    Args:
        subscription_id: Stripe subscription ID
        days: Comma-separated days (MON,TUE,WED,etc.)
        start_time: Start time in HH:MM format
        end_time: End time in HH:MM format  
        location: Service location
        dogs: Number of dogs
        notes: Optional notes
        
    Returns:
        True if successful, False otherwise
    """
    try:
        import stripe
        from stripe_integration import _api
        
        # Get Stripe API instance
        stripe_api = _api()
        
        # Update subscription metadata
        metadata = {
            "days": days,
            "start_time": start_time,
            "end_time": end_time,
            "location": location,
            "dogs": str(dogs),
            "notes": notes
        }
        
        # Add service_code if provided
        if service_code:
            metadata["service_code"] = service_code
        
        updated_subscription = stripe_api.Subscription.modify(
            subscription_id,
            metadata=metadata
        )
        
        logger.info(f"Updated Stripe subscription {subscription_id} metadata")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update Stripe subscription {subscription_id} metadata: {e}")
        return False


def update_local_subscription_schedule(conn: sqlite3.Connection,
                                     subscription_id: str,
                                     days: str,
                                     start_time: str,
                                     end_time: str, 
                                     location: str,
                                     dogs: int,
                                     notes: str = "",
                                     service_code: str = "") -> bool:
    """
    Update local database subscription schedule information with proper error handling.
    
    This function ensures that schedule data is actually persisted in the database,
    preventing issues where the dialog reappears because data wasn't saved.
    
    Args:
        conn: Database connection
        subscription_id: Stripe subscription ID
        days: Comma-separated days (MON,TUE,WED,etc.)
        start_time: Start time in HH:MM format
        end_time: End time in HH:MM format
        location: Service location
        dogs: Number of dogs
        notes: Optional notes
        service_code: Service code for the subscription
        
    Returns:
        True if successful, False otherwise
    """
    try:
        cur = conn.cursor()
        
        # First, ensure the subs_schedule table exists and has all required columns
        cur.execute("""
            CREATE TABLE IF NOT EXISTS subs_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stripe_subscription_id TEXT UNIQUE NOT NULL,
                days TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                dogs INTEGER NOT NULL,
                location TEXT NOT NULL,
                notes TEXT DEFAULT '',
                service_code TEXT DEFAULT '',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Check if service_code column exists, add if missing
        try:
            cur.execute("SELECT service_code FROM subs_schedule LIMIT 1")
        except sqlite3.OperationalError:
            # Column doesn't exist, add it
            cur.execute("ALTER TABLE subs_schedule ADD COLUMN service_code TEXT DEFAULT ''")
            logger.info("Added service_code column to subs_schedule table")
        
        # Insert or update subs_schedule table
        cur.execute("""
            INSERT OR REPLACE INTO subs_schedule 
            (stripe_subscription_id, days, start_time, end_time, dogs, location, notes, service_code, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (subscription_id, days, start_time, end_time, dogs, location, notes, service_code))
        
        # Verify the data was actually saved
        verification = cur.execute("""
            SELECT days, start_time, end_time, location, dogs, service_code 
            FROM subs_schedule 
            WHERE stripe_subscription_id = ?
        """, (subscription_id,)).fetchone()
        
        if not verification:
            logger.error(f"Failed to verify schedule save for subscription {subscription_id}")
            return False
        
        # Log what was actually saved for debugging
        logger.info(f"Successfully saved schedule for subscription {subscription_id}: "
                   f"days={verification[0]}, start={verification[1]}, "
                   f"end={verification[2]}, location={verification[3]}, "
                   f"dogs={verification[4]}, service_code={verification[5] if len(verification) > 5 else ''}")
        
        conn.commit()
        return True
        
    except Exception as e:
        logger.error(f"Failed to update local subscription schedule for {subscription_id}: {e}")
        try:
            conn.rollback()
        except:
            pass
        return False