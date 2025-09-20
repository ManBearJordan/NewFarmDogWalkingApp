"""
Domain rules for the NewFarm Dog Walking App.

This module contains business logic and domain-specific rules
for various service types and booking conditions.
"""

import re


def is_overnight(label_or_code: str) -> bool:
    """
    Check if a service label or code represents an overnight service.
    
    Args:
        label_or_code: Either a service label or service code to check
        
    Returns:
        True if the service is overnight-related, False otherwise
    """
    if not label_or_code or not isinstance(label_or_code, str):
        return False
    
    # Normalize the input - convert to lowercase and remove extra whitespace
    normalized = re.sub(r'\s+', ' ', label_or_code.lower().strip())
    
    # Check if the normalized string contains "overnight" anywhere
    return "overnight" in normalized