"""
Centralized logging utility for subscription error tracking.

This module provides a dedicated logger for subscription-related operations
that writes to a specific error log file for easy diagnostics.
"""

import logging
import os
from datetime import datetime


def get_subscription_logger():
    """
    Get or create the subscription logger with file handler.
    
    Returns:
        Logger instance configured to write to subscription_error_log.txt
    """
    logger = logging.getLogger("subscription_logger")
    
    # Only add handler if it doesn't exist (prevents duplicate handlers)
    if not logger.handlers:
        # Create file handler
        handler = logging.FileHandler("subscription_error_log.txt", encoding='utf-8')
        
        # Create formatter with timestamp, level, and message
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(handler)
        
        # Also add console handler for immediate feedback during development
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # Set logging level to capture all messages
    logger.setLevel(logging.DEBUG)
    
    return logger


def log_subscription_error(message: str, subscription_id: str = None, exception: Exception = None):
    """
    Convenience function to log subscription-related errors.
    
    Args:
        message: Error message to log
        subscription_id: Optional subscription ID for context
        exception: Optional exception object for detailed error info
    """
    logger = get_subscription_logger()
    
    # Build comprehensive error message
    error_msg = message
    if subscription_id:
        error_msg = f"[SUB:{subscription_id}] {error_msg}"
    
    if exception:
        error_msg = f"{error_msg} - Exception: {str(exception)}"
        logger.error(error_msg, exc_info=True)
    else:
        logger.error(error_msg)


def log_subscription_info(message: str, subscription_id: str = None):
    """
    Convenience function to log subscription-related info.
    
    Args:
        message: Info message to log
        subscription_id: Optional subscription ID for context
    """
    logger = get_subscription_logger()
    
    info_msg = message
    if subscription_id:
        info_msg = f"[SUB:{subscription_id}] {info_msg}"
    
    logger.info(info_msg)


def log_subscription_warning(message: str, subscription_id: str = None):
    """
    Convenience function to log subscription-related warnings.
    
    Args:
        message: Warning message to log
        subscription_id: Optional subscription ID for context
    """
    logger = get_subscription_logger()
    
    warning_msg = message
    if subscription_id:
        warning_msg = f"[SUB:{subscription_id}] {warning_msg}"
    
    logger.warning(warning_msg)


def initialize_error_log():
    """
    Initialize the error log file with a header.
    Called at application startup to ensure log file exists.
    """
    log_file = "subscription_error_log.txt"
    
    # Check if log file exists and is recent (today)
    if os.path.exists(log_file):
        # Get file modification time
        mod_time = datetime.fromtimestamp(os.path.getmtime(log_file))
        today = datetime.now().date()
        
        # If log file is from today, don't reinitialize
        if mod_time.date() == today:
            return
    
    # Create or reinitialize log file with header
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"# Subscription Error Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("# This file captures all subscription-related errors for diagnostics\n")
        f.write("# Format: TIMESTAMP LEVEL MESSAGE\n")
        f.write("#" + "="*70 + "\n\n")
    
    # Log initialization
    logger = get_subscription_logger()
    logger.info("Subscription error logging initialized")
