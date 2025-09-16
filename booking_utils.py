"""
Booking utilities with comprehensive error logging for subscription system.

This module provides functions for generating bookings and updating calendars
with robust error tracking and logging capabilities.
"""

import sqlite3
from typing import Dict, Any, Optional
from datetime import datetime, date, timedelta
from log_utils import get_subscription_logger, log_subscription_error, log_subscription_info, log_subscription_warning


def generate_bookings_and_update_calendar(subscription_id: str, schedule_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate bookings and update calendar for a subscription with comprehensive error logging.
    
    Args:
        subscription_id: Stripe subscription ID
        schedule_data: Schedule data dictionary containing days, times, location, etc.
        
    Returns:
        Dictionary with success status and error information
    """
    logger = get_subscription_logger()
    
    try:
        log_subscription_info(f"Starting booking generation for subscription {subscription_id}", subscription_id)
        log_subscription_info(f"Schedule data: {schedule_data}", subscription_id)
        
        # Validate schedule data
        validation_result = validate_schedule_data(subscription_id, schedule_data)
        if not validation_result["valid"]:
            log_subscription_error(f"Schedule validation failed: {validation_result['errors']}", subscription_id)
            return {"success": False, "error": f"Invalid schedule data: {', '.join(validation_result['errors'])}"}
        
        # Get database connection
        try:
            from db import get_db_connection
            conn = get_db_connection()
        except Exception as e:
            log_subscription_error("Failed to get database connection", subscription_id, e)
            return {"success": False, "error": "Database connection failed"}
        
        try:
            # Resolve customer/client information
            client_info = resolve_client_for_subscription(conn, subscription_id)
            if not client_info["success"]:
                log_subscription_error(f"Failed to resolve client: {client_info['error']}", subscription_id)
                return {"success": False, "error": f"Client resolution failed: {client_info['error']}"}
            
            client_id = client_info["client_id"]
            log_subscription_info(f"Resolved client_id: {client_id}", subscription_id)
            
            # Generate booking entries
            booking_result = create_subscription_bookings(conn, subscription_id, client_id, schedule_data)
            if not booking_result["success"]:
                log_subscription_error(f"Booking creation failed: {booking_result['error']}", subscription_id)
                return {"success": False, "error": f"Booking creation failed: {booking_result['error']}"}
            
            # Update calendar/occurrence entries
            calendar_result = update_calendar_occurrences(conn, subscription_id, schedule_data)
            if not calendar_result["success"]:
                log_subscription_warning(f"Calendar update failed: {calendar_result['error']}", subscription_id)
                # Don't fail the entire operation if calendar update fails
            
            conn.commit()
            
            log_subscription_info(f"Successfully generated {booking_result['bookings_created']} bookings for subscription {subscription_id}", subscription_id)
            
            return {
                "success": True,
                "bookings_created": booking_result["bookings_created"],
                "calendar_updated": calendar_result["success"]
            }
            
        except Exception as e:
            conn.rollback()
            log_subscription_error("Exception during booking generation transaction", subscription_id, e)
            return {"success": False, "error": f"Transaction failed: {str(e)}"}
        finally:
            conn.close()
            
    except Exception as e:
        log_subscription_error("Exception during booking generation", subscription_id, e)
        return {"success": False, "error": str(e)}


def validate_schedule_data(subscription_id: str, schedule_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate schedule data for booking generation.
    
    Args:
        subscription_id: Subscription ID for logging context
        schedule_data: Schedule data to validate
        
    Returns:
        Dictionary with validation result and errors
    """
    errors = []
    
    # Required fields
    required_fields = ["days", "start_time", "end_time", "location"]
    for field in required_fields:
        if not schedule_data.get(field):
            errors.append(f"Missing required field: {field}")
    
    # Validate days format
    days = schedule_data.get("days", "")
    if days:
        valid_days = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}
        day_list = [day.strip().upper() for day in days.split(",")]
        invalid_days = [day for day in day_list if day not in valid_days]
        if invalid_days:
            errors.append(f"Invalid days: {invalid_days}")
    
    # Validate time format
    for time_field in ["start_time", "end_time"]:
        time_value = schedule_data.get(time_field, "")
        if time_value:
            try:
                datetime.strptime(time_value, "%H:%M")
            except ValueError:
                errors.append(f"Invalid time format for {time_field}: {time_value}")
    
    # Validate dogs count
    dogs = schedule_data.get("dogs", 1)
    if not isinstance(dogs, int) or dogs < 1 or dogs > 20:
        errors.append(f"Invalid dogs count: {dogs}")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


def resolve_client_for_subscription(conn: sqlite3.Connection, subscription_id: str) -> Dict[str, Any]:
    """
    Resolve client ID for a subscription using Stripe API.
    
    Args:
        conn: Database connection
        subscription_id: Stripe subscription ID
        
    Returns:
        Dictionary with success status and client_id or error
    """
    try:
        # Get subscription from Stripe
        import stripe
        from secrets_config import get_stripe_key
        stripe.api_key = get_stripe_key()
        
        subscription = stripe.Subscription.retrieve(subscription_id, expand=['customer'])
        customer = subscription.customer
        
        if not customer or not hasattr(customer, 'id'):
            return {"success": False, "error": "No customer found in subscription"}
        
        customer_id = customer.id
        
        # Resolve client using unified booking helpers
        from unified_booking_helpers import resolve_client_id
        client_id = resolve_client_id(conn, customer_id)
        
        if not client_id:
            return {"success": False, "error": f"No local client found for Stripe customer {customer_id}"}
        
        return {"success": True, "client_id": client_id, "customer_id": customer_id}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_subscription_bookings(conn: sqlite3.Connection, subscription_id: str, client_id: int, schedule_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create booking entries for a subscription.
    
    Args:
        conn: Database connection
        subscription_id: Subscription ID
        client_id: Local client ID
        schedule_data: Schedule data
        
    Returns:
        Dictionary with success status and booking count
    """
    try:
        # Parse schedule data
        days_csv = schedule_data["days"]
        start_time = schedule_data["start_time"]
        end_time = schedule_data["end_time"]
        location = schedule_data["location"]
        dogs = schedule_data.get("dogs", 1)
        notes = schedule_data.get("notes", "")
        service_code = schedule_data.get("service_code", "WALK_SHORT_SINGLE")
        
        # Convert days to bitmask
        day_mapping = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}
        days_mask = 0
        for day in days_csv.split(","):
            day = day.strip().upper()
            if day in day_mapping:
                days_mask |= (1 << day_mapping[day])
        
        # Use unified booking helpers to rebuild bookings
        from unified_booking_helpers import purge_future_subscription_bookings, rebuild_subscription_bookings
        
        # First, purge existing future bookings
        purge_future_subscription_bookings(conn, subscription_id)
        
        # Generate new bookings
        bookings_created = rebuild_subscription_bookings(
            conn, subscription_id, days_mask, start_time, end_time,
            dogs, location, notes, months_ahead=3
        )
        
        return {"success": True, "bookings_created": bookings_created}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def update_calendar_occurrences(conn: sqlite3.Connection, subscription_id: str, schedule_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update calendar occurrence entries for a subscription.
    
    Args:
        conn: Database connection
        subscription_id: Subscription ID
        schedule_data: Schedule data
        
    Returns:
        Dictionary with success status
    """
    try:
        cur = conn.cursor()
        
        # Delete existing occurrences
        cur.execute("""
            DELETE FROM sub_occurrences 
            WHERE stripe_subscription_id = ? 
            AND start_dt >= date('now')
        """, (subscription_id,))
        
        # Generate new occurrences (simplified version)
        days_csv = schedule_data["days"]
        start_time = schedule_data["start_time"]
        end_time = schedule_data["end_time"]
        location = schedule_data["location"]
        
        # Generate occurrences for next 3 months
        today = date.today()
        end_date = today + timedelta(days=90)
        
        day_mapping = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}
        selected_days = set()
        for day in days_csv.split(","):
            day = day.strip().upper()
            if day in day_mapping:
                selected_days.add(day_mapping[day])
        
        occurrences_created = 0
        current_date = today
        
        while current_date <= end_date:
            weekday = current_date.weekday()  # Mon=0, Tue=1, etc.
            
            if weekday in selected_days:
                start_dt = datetime.combine(current_date, datetime.strptime(start_time, "%H:%M").time())
                end_dt = datetime.combine(current_date, datetime.strptime(end_time, "%H:%M").time())
                
                cur.execute("""
                    INSERT INTO sub_occurrences (
                        stripe_subscription_id, start_dt, end_dt, location, status
                    ) VALUES (?, ?, ?, ?, 'scheduled')
                """, (subscription_id, start_dt.isoformat(), end_dt.isoformat(), location))
                
                occurrences_created += 1
            
            current_date += timedelta(days=1)
        
        return {"success": True, "occurrences_created": occurrences_created}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
