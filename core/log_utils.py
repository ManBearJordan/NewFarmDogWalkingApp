"""Simple file logging utility for subscription sync operations."""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional


def log_subscription_error(message: str, error_file: str = "subscription_error_log.txt") -> None:
    """Log subscription sync errors to a file.
    
    Args:
        message: Error message to log
        error_file: Name of the error log file (default: subscription_error_log.txt)
    """
    # Determine log file path relative to Django project root
    try:
        from django.conf import settings
        log_path = Path(settings.BASE_DIR) / error_file
    except ImportError:
        # Fallback if Django not available
        log_path = Path.cwd() / error_file
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        # Fallback to print if file writing fails
        print(f"Failed to write to log file {log_path}: {e}")
        print(f"Original log message: {log_entry.strip()}")


def log_subscription_info(message: str, info_file: str = "subscription_sync_log.txt") -> None:
    """Log subscription sync info messages to a file.
    
    Args:
        message: Info message to log
        info_file: Name of the info log file (default: subscription_sync_log.txt)
    """
    # Determine log file path relative to Django project root
    try:
        from django.conf import settings
        log_path = Path(settings.BASE_DIR) / info_file
    except ImportError:
        # Fallback if Django not available
        log_path = Path.cwd() / info_file
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        # Fallback to print if file writing fails
        print(f"Failed to write to log file {log_path}: {e}")
        print(f"Original log message: {log_entry.strip()}")


def clear_log_file(log_file: str) -> bool:
    """Clear contents of a log file.
    
    Args:
        log_file: Name of the log file to clear
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from django.conf import settings
        log_path = Path(settings.BASE_DIR) / log_file
    except ImportError:
        # Fallback if Django not available
        log_path = Path.cwd() / log_file
    
    try:
        if log_path.exists():
            log_path.unlink()
        return True
    except Exception as e:
        log_subscription_error(f"Failed to clear log file {log_path}: {e}")
        return False