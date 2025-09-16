"""
Subscription validation and missing data detection for the unified subscription workflow.

This module provides functions to validate subscriptions and identify which ones
are missing required schedule information (days, time, location, dog count).
"""

import sqlite3
from typing import List, Dict, Any, Optional
from subscription_sync import extract_schedule_from_subscription
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
    
    Args:
        subscription: Subscription data from Stripe API
        
    Returns:
        True if schedule is complete, False otherwise
    """
    schedule = extract_schedule_from_subscription(subscription)
    
    # All required fields must be present and valid
    return (
        len(schedule.get("day_list", [])) > 0 and
        schedule.get("start_time", "") not in ("", "09:00") and  
        schedule.get("end_time", "") not in ("", "10:00") and
        schedule.get("location", "").strip() != "" and
        schedule.get("dogs", 0) > 0
    )


def update_stripe_subscription_metadata(subscription_id: str, 
                                       days: str,
                                       start_time: str, 
                                       end_time: str,
                                       location: str,
                                       dogs: int,
                                       notes: str = "") -> bool:
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
        updated_subscription = stripe_api.Subscription.modify(
            subscription_id,
            metadata={
                "days": days,
                "start_time": start_time,
                "end_time": end_time,
                "location": location,
                "dogs": str(dogs),
                "notes": notes
            }
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
                                     notes: str = "") -> bool:
    """
    Update local database subscription schedule information.
    
    Args:
        conn: Database connection
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
        # Insert or update subs_schedule table
        conn.execute("""
            INSERT OR REPLACE INTO subs_schedule 
            (stripe_subscription_id, days, start_time, end_time, dogs, location, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (subscription_id, days, start_time, end_time, dogs, location, notes))
        
        conn.commit()
        logger.info(f"Updated local subscription schedule for {subscription_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update local subscription schedule for {subscription_id}: {e}")
        return False