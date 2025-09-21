"""
Custom template filters for consistent money formatting.

Provides filters to format money amounts from cents to dollar display.
"""

from django import template

register = template.Library()


@register.filter
def money_format(cents):
    """
    Format cents as money with consistent $cents/100:.2f formatting.
    
    Args:
        cents: Integer amount in cents
        
    Returns:
        str: Formatted money string like "$20.00"
    """
    if cents is None:
        return "$0.00"
    
    try:
        dollars = float(cents) / 100.0
        return f"${dollars:.2f}"
    except (ValueError, TypeError):
        return "$0.00"


@register.filter
def money_format_no_symbol(cents):
    """
    Format cents as money without the dollar symbol.
    
    Args:
        cents: Integer amount in cents
        
    Returns:
        str: Formatted money string like "20.00"
    """
    if cents is None:
        return "0.00"
    
    try:
        dollars = float(cents) / 100.0
        return f"{dollars:.2f}"
    except (ValueError, TypeError):
        return "0.00"