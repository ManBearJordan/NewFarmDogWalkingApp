"""
Utility functions for integrating Django StripeSettings with existing Stripe key management.

This module provides bridge functions that allow the existing stripe_key_manager.py
to work with the new Django-based StripeSettings model, enabling web-based key entry
via Django admin while maintaining backward compatibility.
"""

def get_stripe_key_from_django():
    """
    Get Stripe key from Django StripeSettings model.
    
    This function bridges the existing stripe_key_manager system with the new
    Django-based settings. It should be called by stripe_key_manager as a fallback
    when keyring or environment variables don't have a key.
    
    Returns:
        str: Stripe API key if available, None otherwise
    """
    try:
        from core.models import StripeSettings
        return StripeSettings.get_stripe_key()
    except Exception:
        return None


def set_stripe_key_in_django(api_key):
    """
    Set Stripe key in Django StripeSettings model.
    
    This function allows external systems to set the Stripe key in Django.
    
    Args:
        api_key (str): The Stripe API key to store
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from core.models import StripeSettings
        return StripeSettings.set_stripe_key(api_key)
    except Exception:
        return False


def get_stripe_key_unified():
    """
    Unified function to get Stripe key from any available source.
    
    This function checks multiple sources in order:
    1. Django StripeSettings (web admin)
    2. Existing stripe_key_manager (keyring/env vars)
    
    This should be used by stripe_integration.py and other modules that need
    the Stripe key, ensuring web-based keys take precedence.
    
    Returns:
        str: Stripe API key if available from any source, None otherwise
    """
    # First try Django StripeSettings (web admin)
    django_key = get_stripe_key_from_django()
    if django_key:
        return django_key
    
    # Fallback to existing stripe_key_manager
    try:
        from stripe_key_manager import get_stripe_key
        return get_stripe_key()
    except Exception:
        return None