"""
Comprehensive error handling and logging for subscription workflow operations.

This module provides centralized error handling, logging, and user feedback
for all subscription-related operations to ensure robust error recovery
and clear communication to users.
"""

import logging
from typing import Optional, Dict, Any
from PySide6.QtWidgets import QMessageBox, QWidget

logger = logging.getLogger(__name__)


class SubscriptionWorkflowError(Exception):
    """Custom exception for subscription workflow errors."""
    
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


def log_subscription_error(operation: str, subscription_id: str, error: Exception, 
                          context: Dict[str, Any] = None) -> str:
    """
    Log subscription error with full context for debugging.
    
    Args:
        operation: Description of the operation that failed
        subscription_id: Stripe subscription ID
        error: The exception that occurred
        context: Additional context information
        
    Returns:
        Formatted error message for user display
    """
    error_id = f"{operation}_{subscription_id}_{hash(str(error)) % 10000}"
    
    # Log full error details
    logger.error(
        f"SUBSCRIPTION_ERROR [{error_id}]: {operation} failed for subscription {subscription_id}",
        extra={
            "error_id": error_id,
            "operation": operation,
            "subscription_id": subscription_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context or {}
        }
    )
    
    # Return user-friendly message
    return f"Operation '{operation}' failed for subscription {subscription_id[:12]}... (Error ID: {error_id})"


def show_error_dialog(parent: QWidget, title: str, message: str, details: str = None):
    """
    Show a user-friendly error dialog with optional detailed information.
    
    Args:
        parent: Parent widget
        title: Dialog title
        message: Main error message
        details: Optional detailed error information
    """
    try:
        # Skip GUI dialog if no display available (headless environment)
        if not parent or not hasattr(parent, 'show'):
            print(f"ERROR: {title} - {message}")
            if details:
                print(f"Details: {details}")
            return
            
        from PySide6.QtWidgets import QMessageBox
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        if details:
            msg_box.setDetailedText(details)
            
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec()
        
    except Exception as dialog_error:
        # Fallback if dialog creation fails
        logger.error(f"Failed to show error dialog: {dialog_error}")
        print(f"ERROR: {title} - {message}")
        if details:
            print(f"Details: {details}")


def show_warning_dialog(parent: QWidget, title: str, message: str, 
                       show_retry: bool = False) -> bool:
    """
    Show a warning dialog with optional retry button.
    
    Args:
        parent: Parent widget
        title: Dialog title
        message: Warning message
        show_retry: Whether to show a retry button
        
    Returns:
        True if user clicked retry (when show_retry=True), False otherwise
    """
    try:
        # Skip GUI dialog if no display available (headless environment)
        if not parent or not hasattr(parent, 'show'):
            print(f"WARNING: {title} - {message}")
            return False
            
        from PySide6.QtWidgets import QMessageBox
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        if show_retry:
            msg_box.setStandardButtons(QMessageBox.Retry | QMessageBox.Cancel)
            result = msg_box.exec()
            return result == QMessageBox.Retry
        else:
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec()
            return False
            
    except Exception as dialog_error:
        logger.error(f"Failed to show warning dialog: {dialog_error}")
        print(f"WARNING: {title} - {message}")
        return False


def handle_stripe_api_error(error: Exception, operation: str, subscription_id: str = None) -> str:
    """
    Handle Stripe API errors with appropriate logging and user messages.
    
    Args:
        error: The Stripe API error
        operation: Description of the operation
        subscription_id: Optional subscription ID
        
    Returns:
        User-friendly error message
    """
    error_msg = str(error)
    
    # Common Stripe error patterns
    if "rate_limit" in error_msg.lower():
        user_msg = "Rate limit exceeded. Please try again in a few moments."
    elif "invalid_request" in error_msg.lower():
        user_msg = "Invalid request to Stripe. Please check the subscription details."
    elif "authentication" in error_msg.lower():
        user_msg = "Stripe API authentication failed. Please check API key configuration."
    elif "network" in error_msg.lower() or "connection" in error_msg.lower():
        user_msg = "Network error connecting to Stripe. Please check your internet connection."
    else:
        user_msg = f"Stripe API error: {error_msg}"
    
    # Log the error
    context = {"operation": operation}
    if subscription_id:
        context["subscription_id"] = subscription_id
        
    log_subscription_error(f"Stripe API - {operation}", subscription_id or "unknown", error, context)
    
    return user_msg


def handle_database_error(error: Exception, operation: str, subscription_id: str = None) -> str:
    """
    Handle database errors with appropriate logging and user messages.
    
    Args:
        error: The database error
        operation: Description of the operation
        subscription_id: Optional subscription ID
        
    Returns:
        User-friendly error message
    """
    error_msg = str(error)
    
    # Common database error patterns
    if "unique constraint" in error_msg.lower():
        user_msg = "Data conflict detected. The record may already exist."
    elif "foreign key" in error_msg.lower():
        user_msg = "Data reference error. Required related data may be missing."
    elif "no such table" in error_msg.lower():
        user_msg = "Database table missing. Please restart the application."
    elif "database is locked" in error_msg.lower():
        user_msg = "Database is busy. Please try again in a moment."
    else:
        user_msg = f"Database error: {error_msg}"
    
    # Log the error
    context = {"operation": operation}
    if subscription_id:
        context["subscription_id"] = subscription_id
        
    log_subscription_error(f"Database - {operation}", subscription_id or "unknown", error, context)
    
    return user_msg


def validate_subscription_data(subscription_data: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate subscription data and return validation result.
    
    Args:
        subscription_data: Subscription data to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not subscription_data:
        return False, "Subscription data is empty"
        
    if not subscription_data.get("id"):
        return False, "Subscription ID is missing"
        
    # Check for customer information
    customer = subscription_data.get("customer")
    if not customer:
        return False, "Customer information is missing"
        
    # If customer is just an ID string, that's fine
    if isinstance(customer, str):
        if not customer.startswith("cus_"):
            return False, "Invalid customer ID format"
    elif isinstance(customer, dict):
        if not customer.get("id", "").startswith("cus_"):
            return False, "Invalid customer ID in customer object"
    else:
        # Customer object from Stripe API
        if not getattr(customer, "id", "").startswith("cus_"):
            return False, "Invalid customer ID in customer object"
    
    return True, ""


def safe_execute_with_retry(operation_func, max_retries: int = 3, 
                           operation_name: str = "operation") -> tuple[bool, Any, str]:
    """
    Safely execute an operation with retry logic.
    
    Args:
        operation_func: Function to execute
        max_retries: Maximum number of retry attempts
        operation_name: Name of the operation for logging
        
    Returns:
        Tuple of (success, result, error_message)
    """
    for attempt in range(max_retries):
        try:
            result = operation_func()
            return True, result, ""
            
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"{operation_name} attempt {attempt + 1} failed, retrying: {e}")
                continue
            else:
                error_msg = f"{operation_name} failed after {max_retries} attempts: {e}"
                logger.error(error_msg)
                return False, None, str(e)
    
    return False, None, "Maximum retries exceeded"