"""
Custom template filters for consistent money formatting.

Provides filters to format money amounts from cents to dollar display.
"""

from django import template
import math

register = template.Library()

def _fmt_money(amount_float: float) -> str:
    return "${:,.2f}".format(amount_float)

@register.filter(name="cents_to_dollars")
def cents_to_dollars(value):
    """
    2500 -> $25.00 ; None/""/invalid -> "—"
    """
    try:
        if value is None or value == "" or value is False:
            return "—"
        cents = int(value)
        return _fmt_money(cents / 100.0)
    except Exception:
        return "—"

@register.filter(name="dollars")
def dollars(value):
    """
    25 -> $25.00 ; 25.5 -> $25.50 ; None -> "—"
    """
    try:
        if value is None or value == "" or value is False:
            return "—"
        return _fmt_money(float(value))
    except Exception:
        return "—"


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