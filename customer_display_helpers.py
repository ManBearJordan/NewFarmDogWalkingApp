"""
Robust customer display helpers that ensure "Unknown Customer" issues are resolved.

This module provides centralized functions for displaying customer information
that always fall back to Stripe API when local mapping fails, as per problem statement.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from log_utils import get_subscription_logger, log_subscription_error, log_subscription_warning

logger = logging.getLogger(__name__)


def get_robust_customer_display_info(subscription_data: Dict[str, Any]) -> str:
    """
    Get customer display information with robust fallback to Stripe API.
    
    This function ensures we NEVER show "Unknown Customer" unless there's
    absolutely no customer data available. It follows this hierarchy:
    
    1. Use expanded customer data from subscription if available
    2. Fetch directly from Stripe API using customer ID
    3. Use customer ID as last resort
    4. Only show "Unknown Customer" if no customer ID exists
    
    Args:
        subscription_data: Subscription data from Stripe API
        
    Returns:
        Customer display string (name, email, or customer ID)
    """
    subscription_id = subscription_data.get("id", "unknown")
    error_logger = get_subscription_logger()
    
    try:
        # Step 1: Check if customer data is already expanded in subscription
        customer = subscription_data.get("customer", {})
        
        # Handle different customer data formats
        name = ""
        email = ""
        customer_id = ""
        
        try:
            if hasattr(customer, 'startswith') and callable(customer.startswith):
                # Customer is just an ID string
                name = ""
                email = ""
                customer_id = customer
            elif hasattr(customer, 'get') and callable(customer.get):
                # Customer is dict-like
                name = customer.get("name", "")
                email = customer.get("email", "")
                customer_id = customer.get("id", "")
            elif customer:
                # Customer is an object from Stripe API
                name = getattr(customer, "name", "")
                email = getattr(customer, "email", "")
                customer_id = getattr(customer, "id", "")
                
                # Handle case where customer_id is empty string
                if not customer_id:
                    name = ""
                    email = ""
            else:
                name = ""
                email = ""
                customer_id = ""
        except Exception:
            name = ""
            email = ""
            customer_id = ""
        
        # If we have good expanded data, use it
        if name and email:
            return f"{name} ({email})"
        elif name:
            return name
        elif email:
            return email
        
        # Step 2: If we don't have good data but have customer_id, fetch from Stripe
        if customer_id:
            try:
                from stripe_integration import _api
                stripe_api = _api()
                error_logger.debug(f"[SUB:{subscription_id}] Fetching customer details from Stripe for {customer_id}")
                
                customer_obj = stripe_api.Customer.retrieve(customer_id)
                fetched_name = getattr(customer_obj, "name", "") or ""
                fetched_email = getattr(customer_obj, "email", "") or ""
                
                if fetched_name and fetched_email:
                    return f"{fetched_name} ({fetched_email})"
                elif fetched_name:
                    return fetched_name
                elif fetched_email:
                    return fetched_email
                else:
                    # Last resort - use customer ID 
                    log_subscription_warning(f"Customer {customer_id} has no name or email in Stripe", subscription_id)
                    return f"Customer {customer_id}"
                    
            except Exception as e:
                log_subscription_error(f"Stripe API failed for customer {customer_id}", subscription_id, e)
                # Still better to show customer ID than "Unknown Customer"
                return f"Customer {customer_id} (Stripe API error)"
        
        # Step 3: No customer ID available
        log_subscription_error("Unknown Customer: No name, email, or customer_id found in subscription_data", subscription_id)
        return "Unknown Customer"
        
    except Exception as e:
        log_subscription_error("Display info error", subscription_id, e)
        return "Unknown Customer"


def get_customer_info_with_fallback(customer_data: Any) -> Tuple[str, str, str]:
    """
    Extract customer information with Stripe API fallback.
    
    Args:
        customer_data: Customer data (dict, object, or customer ID string)
        
    Returns:
        Tuple of (display_name, name, email)
    """
    name = ""
    email = ""
    customer_id = ""
    
    try:
        # Handle different customer data formats
        if hasattr(customer_data, 'get') and callable(customer_data.get):
            # Dict-like customer data
            name = customer_data.get("name", "")
            email = customer_data.get("email", "")
            customer_id = customer_data.get("id", "")
        elif hasattr(customer_data, 'startswith') and callable(customer_data.startswith):
            # Customer ID string
            customer_id = customer_data
        elif customer_data:
            # Customer object
            name = getattr(customer_data, "name", "")
            email = getattr(customer_data, "email", "")
            customer_id = getattr(customer_data, "id", "")
        
        # If we have good data already, return it
        if name or email:
            if name and email:
                display_name = f"{name} ({email})"
            else:
                display_name = name or email
            return display_name, name, email
        
        # Fetch from Stripe if we have customer ID but no name/email
        if customer_id:
            try:
                from stripe_integration import _api
                stripe_api = _api()
                customer_obj = stripe_api.Customer.retrieve(customer_id)
                
                fetched_name = getattr(customer_obj, "name", "") or ""
                fetched_email = getattr(customer_obj, "email", "") or ""
                
                if fetched_name and fetched_email:
                    display_name = f"{fetched_name} ({fetched_email})"
                elif fetched_name or fetched_email:
                    display_name = fetched_name or fetched_email
                else:
                    display_name = f"Customer {customer_id}"
                    
                return display_name, fetched_name, fetched_email
                
            except Exception as e:
                logger.warning(f"Failed to fetch customer from Stripe: {e}")
                return f"Customer {customer_id}", "", ""
        
        return "Unknown Customer", "", ""
        
    except Exception as e:
        logger.error(f"Error processing customer info: {e}")
        return "Unknown Customer", "", ""


def ensure_customer_data_in_subscription(subscription_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure subscription data has proper customer information, fetching from Stripe if needed.
    
    This modifies the subscription data in-place to add customer details.
    
    Args:
        subscription_data: Subscription data dictionary
        
    Returns:
        Modified subscription data with customer info
    """
    try:
        customer = subscription_data.get("customer")
        
        # If customer is just an ID string, fetch the full customer object
        if isinstance(customer, str):
            try:
                from stripe_integration import _api
                stripe_api = _api()
                customer_obj = stripe_api.Customer.retrieve(customer)
                
                # Replace customer ID with full customer data
                subscription_data["customer"] = {
                    "id": customer_obj.id,
                    "name": getattr(customer_obj, "name", "") or "",
                    "email": getattr(customer_obj, "email", "") or "",
                    "phone": getattr(customer_obj, "phone", "") or "",
                }
                
            except Exception as e:
                logger.warning(f"Failed to expand customer data for {customer}: {e}")
        
        # If customer data exists but is missing name/email, try to fetch it
        elif hasattr(customer, 'get') and callable(customer.get) and customer.get("id"):
            customer_id = customer.get("id")
            if not customer.get("name") and not customer.get("email"):
                try:
                    from stripe_integration import _api
                    stripe_api = _api()
                    customer_obj = stripe_api.Customer.retrieve(customer_id)
                    
                    # Update with fetched data
                    customer["name"] = getattr(customer_obj, "name", "") or ""
                    customer["email"] = getattr(customer_obj, "email", "") or ""
                    customer["phone"] = getattr(customer_obj, "phone", "") or ""
                    
                except Exception as e:
                    logger.warning(f"Failed to fetch missing customer data for {customer_id}: {e}")
        
        return subscription_data
        
    except Exception as e:
        logger.error(f"Error ensuring customer data in subscription: {e}")
        return subscription_data
