"""
Central service mapping for all service display and code lookups.

This module provides unified mapping between service codes and display names
for all booking, calendar, Stripe import, and UI logic across the application.
The mapping matches exactly the 26 prices and products configured in Stripe.
"""

# Central mapping from service codes to display names (exactly 26 services)
SERVICE_CODE_TO_DISPLAY = {
    "PICKUP_DROPOFF": "Pick up/Drop off",
    "PICKUP_FORTNIGHTLY_PER_VISIT": "Pick up/Drop off (Fortnightly per visit)",
    "PICKUP_WEEKLY_PER_VISIT": "Pick up/Drop off (Weekly per visit)",
    "DAYCARE_SINGLE": "Doggy Daycare (per day)",
    "DAYCARE_FORTNIGHTLY_PER_VISIT": "Doggy Daycare (Fortnightly per visit)",
    "DAYCARE_WEEKLY": "Doggy Daycare (Weekly)",
    "DAYCARE_PACK5": "Doggy Daycare (Pack x5)",
    "HOME_30WEEKLY": "Home Visit 1/day (weekly)",
    "HOME_30_2_DAY_WEEKLY": "Home Visit 2/day (weekly)",
    "HV_30_1X_SINGLE": "Home Visit 30m 1× (Single)",
    "HV_30_1X_PACK5": "Home Visit 30m 1× (Pack x5)",
    "HV_30_2X_SINGLE": "Home Visit 30m 2× (Single)",
    "HV_30_2X_PACK5": "Home Visit 30m 2× (Pack x5)",
    "WALK_LONG_SINGLE": "Long Walk (Single)",
    "WALK_LONG_PACK5": "Long Walk (Pack x5)",
    "WALK_SHORT_SINGLE": "Short Walk (Single)",
    "WALK_SHORT_PACK5": "Short Walk (Pack x5)",
    "WALK_LONG_WEEKLY": "Long Walk (Weekly)",
    "WALK_SHORT_WEEKLY": "Short Walk (Weekly)",
    "SCOOP_TWICE_WEEKLY_MONTH": "Poop Scoop – Twice Weekly (Monthly)",
    "SCOOP_FORTNIGHTLY_MONTH": "Poop Scoop – Fortnightly (Monthly)",
    "SCOOP_WEEKLY_MONTH": "Poop Scoop – Weekly (Monthly)",
    "SCOOP_ONCE_SINGLE": "Poop Scoop – One-time",
    "BOARD_OVERNIGHT_SINGLE": "Overnight Pet Sitting (Single)",
    "BOARD_OVERNIGHT_PACK5": "Overnight Pet Sitting (Pack x5)",
    "PICKUP_DROPOFF_PACK5": "Pick up/Drop off (Pack x5)",
}

# Reverse mapping from display names to service codes
DISPLAY_TO_SERVICE_CODE = {v: k for k, v in SERVICE_CODE_TO_DISPLAY.items()}


def get_service_display_name(service_code: str, default: str = "") -> str:
    """
    Get the display name for a service code.
    
    Args:
        service_code: The service code (e.g., "WALK_SHORT_SINGLE")
        default: Default value if service code is not found
        
    Returns:
        The display name or default if not found
    """
    if not service_code:
        return default or "Service"
    
    return SERVICE_CODE_TO_DISPLAY.get(service_code, default or service_code.replace("_", " ").title())


def get_service_code(display_name: str, default: str = "") -> str:
    """
    Get the service code for a display name.
    
    Args:
        display_name: The display name (e.g., "Short Walk (Single)")
        default: Default value if display name is not found
        
    Returns:
        The service code or default if not found
    """
    if not display_name:
        return default
        
    return DISPLAY_TO_SERVICE_CODE.get(display_name, default)


def get_all_service_codes() -> list[str]:
    """Get all available service codes."""
    return list(SERVICE_CODE_TO_DISPLAY.keys())


def get_all_display_names() -> list[str]:
    """Get all available display names."""
    return list(SERVICE_CODE_TO_DISPLAY.values())


def is_valid_service_code(service_code: str) -> bool:
    """Check if a service code is valid."""
    return service_code in SERVICE_CODE_TO_DISPLAY


def is_valid_display_name(display_name: str) -> bool:
    """Check if a display name is valid."""
    return display_name in DISPLAY_TO_SERVICE_CODE