"""
Stripe Secret Key Manager

This module provides secure storage and retrieval of Stripe secret keys using the system's
credential manager (Windows Credential Manager, macOS Keychain, or Linux Secret Service).

The module uses the keyring library which provides cross-platform access to secure credential
storage systems. Keys are never stored in plaintext and are retrieved securely at runtime.

Usage:
    from stripe_key_manager import get_stripe_key, set_stripe_key
    
    # On first run, prompt user and store key
    key = get_stripe_key()
    if not key:
        new_key = input("Enter your Stripe secret key: ")
        set_stripe_key(new_key)
        key = new_key
    
    # Use key with Stripe
    import stripe
    stripe.api_key = key
"""

import os
import sys
from typing import Optional

# Try to import keyring, but provide fallback for development/testing
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    print("Warning: keyring library not available. Falling back to environment variables.")
    KEYRING_AVAILABLE = False

# Configuration constants
SERVICE_NAME = "NewFarmDogWalkingApp"
KEY_NAME = "stripe_secret_key"

def get_stripe_key() -> str:
    """
    Retrieve the Stripe secret key from secure storage.
    
    Returns:
        str: The Stripe secret key, or empty string if not found
    """
    if KEYRING_AVAILABLE:
        try:
            key = keyring.get_password(SERVICE_NAME, KEY_NAME)
            if key:
                return key
        except Exception as e:
            print(f"Warning: Could not retrieve key from secure storage: {e}")
    
    # Fallback to environment variables (less secure but better than hardcoded)
    return os.getenv("STRIPE_SECRET_KEY") or os.getenv("STRIPE_API_KEY") or ""


def set_stripe_key(key: str) -> bool:
    """
    Store the Stripe secret key in secure storage.
    
    Args:
        key (str): The Stripe secret key to store
        
    Returns:
        bool: True if the key was successfully stored, False otherwise
    """
    if not key or not key.strip():
        print("Error: Cannot store empty key")
        return False
    
    # Validate that it looks like a Stripe key
    key = key.strip()
    if not (key.startswith("sk_test_") or key.startswith("sk_live_")):
        print("Warning: Key doesn't appear to be a valid Stripe secret key (should start with sk_test_ or sk_live_)")
        # Continue anyway in case it's a valid key with different format
    
    if KEYRING_AVAILABLE:
        try:
            keyring.set_password(SERVICE_NAME, KEY_NAME, key)
            print("Stripe secret key stored securely in system credential manager")
            return True
        except Exception as e:
            print(f"Error: Could not store key in secure storage: {e}")
            print("Note: Key was not stored. You may need to run as administrator or check your system's credential manager.")
            return False
    else:
        print("Warning: Keyring not available. Consider setting STRIPE_SECRET_KEY environment variable.")
        return False


def delete_stripe_key() -> bool:
    """
    Delete the Stripe secret key from secure storage.
    
    Returns:
        bool: True if the key was successfully deleted, False otherwise
    """
    if KEYRING_AVAILABLE:
        try:
            keyring.delete_password(SERVICE_NAME, KEY_NAME)
            print("Stripe secret key deleted from secure storage")
            return True
        except keyring.errors.PasswordDeleteError:
            print("No Stripe key found in secure storage to delete")
            return True
        except Exception as e:
            print(f"Error: Could not delete key from secure storage: {e}")
            return False
    else:
        print("Warning: Keyring not available. No secure key storage to delete from.")
        return False


def prompt_for_stripe_key() -> Optional[str]:
    """
    Prompt the user to enter their Stripe secret key.
    
    Returns:
        str: The entered key, or None if user cancelled
    """
    print("\n" + "="*60)
    print("STRIPE SECRET KEY SETUP")
    print("="*60)
    print("This application needs your Stripe secret key to process payments.")
    print("Your key will be stored securely in your system's credential manager.")
    print("Keys are never stored in plaintext or committed to version control.")
    print("\nTo find your Stripe secret key:")
    print("1. Log in to your Stripe Dashboard")
    print("2. Go to Developers > API keys")
    print("3. Copy the 'Secret key' (starts with sk_test_ or sk_live_)")
    print("\nFor development, use a test key (sk_test_...)")
    print("For production, use a live key (sk_live_...)")
    print("-"*60)
    
    try:
        key = input("Enter your Stripe secret key (or press Enter to skip): ").strip()
        if not key:
            print("Setup skipped. You can run this setup again later.")
            return None
        return key
    except KeyboardInterrupt:
        print("\nSetup cancelled.")
        return None
    except EOFError:
        print("\nInput not available. Please set STRIPE_SECRET_KEY environment variable manually.")
        return None


def ensure_stripe_key() -> str:
    """
    Ensure a Stripe key is available, prompting the user if necessary.
    
    This is the main function to call when initializing the application.
    It will:
    1. Try to get an existing key from secure storage
    2. If no key found, prompt the user to enter one
    3. Store the new key securely
    4. Return the key for use
    
    Returns:
        str: The Stripe secret key, or empty string if none available
    """
    # First try to get existing key
    key = get_stripe_key()
    if key:
        return key
    
    # No key found, prompt user
    key = prompt_for_stripe_key()
    if not key:
        return ""
    
    # Try to store the key
    if set_stripe_key(key):
        return key
    else:
        print("Warning: Key could not be stored securely, but will be used for this session.")
        return key


def get_key_status() -> dict:
    """
    Get information about the current key storage status.
    
    Returns:
        dict: Status information including whether a key is stored, keyring availability, etc.
    """
    key_stored = bool(get_stripe_key())
    
    status = {
        "key_stored": key_stored,
        "keyring_available": KEYRING_AVAILABLE,
        "storage_method": "keyring" if KEYRING_AVAILABLE else "environment_variables",
        "service_name": SERVICE_NAME,
        "key_name": KEY_NAME
    }
    
    if key_stored:
        key = get_stripe_key()
        if key.startswith("sk_test_"):
            status["key_type"] = "test"
        elif key.startswith("sk_live_"):
            status["key_type"] = "live"
        else:
            status["key_type"] = "unknown"
    else:
        status["key_type"] = None
    
    return status


if __name__ == "__main__":
    """Command line interface for key management"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "status":
            status = get_key_status()
            print("\nStripe Key Status:")
            print(f"  Key stored: {status['key_stored']}")
            print(f"  Key type: {status['key_type'] or 'None'}")
            print(f"  Keyring available: {status['keyring_available']}")
            print(f"  Storage method: {status['storage_method']}")
            
        elif command == "set":
            key = prompt_for_stripe_key()
            if key:
                set_stripe_key(key)
                
        elif command == "delete":
            confirm = input("Are you sure you want to delete the stored Stripe key? (y/N): ")
            if confirm.lower().startswith('y'):
                delete_stripe_key()
            else:
                print("Deletion cancelled.")
                
        elif command == "get":
            key = get_stripe_key()
            if key:
                # Only show first and last few characters for security
                if len(key) > 8:
                    masked = key[:8] + "..." + key[-4:]
                else:
                    masked = key[:2] + "..." + key[-2:]
                print(f"Key found: {masked}")
            else:
                print("No key found")
                
        else:
            print("Usage: python stripe_key_manager.py [status|set|delete|get]")
    else:
        # Interactive setup
        key = ensure_stripe_key()
        if key:
            print(f"\nSetup complete! Key type: {'test' if key.startswith('sk_test_') else 'live'}")
        else:
            print("\nNo key configured. The application will not be able to process Stripe payments.")