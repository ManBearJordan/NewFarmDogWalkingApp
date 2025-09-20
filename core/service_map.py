"""
Service mapping utilities for the NewFarm Dog Walking App.

This module provides mapping between display labels and service codes,
with fuzzy matching capabilities for resolving service information.
"""

from typing import Dict, Optional, Tuple
import re


# Constant dictionary mapping common display labels to canonical service codes
DISPLAY_TO_SERVICE_CODE: Dict[str, str] = {
    # Walk services
    "walk": "walk",
    "dog walk": "walk", 
    "walking": "walk",
    "30 minute walk": "walk_30min",
    "30min walk": "walk_30min",
    "30 min walk": "walk_30min",
    "quick walk": "walk_30min",
    "1 hour walk": "walk_1hr",
    "1hr walk": "walk_1hr", 
    "1 hr walk": "walk_1hr",
    "standard walk": "walk_1hr",
    "long walk": "walk_1hr",
    "weekly walk": "weekly_walk",
    "pack walk": "pack_walk",
    "group walk": "pack_walk",
    
    # Daycare services
    "daycare": "daycare",
    "day care": "daycare",
    "dog daycare": "daycare",
    "full day": "daycare",
    
    # Home visit services
    "home visit": "home_visit",
    "home check": "home_visit",
    "house visit": "home_visit",
    "wellness check": "home_visit",
    
    # Pickup services
    "pickup": "pickup",
    "pick up": "pickup",
    "collection": "pickup",
    "transport": "pickup",
    
    # Poop scoop services
    "poop scoop": "poop_scoop",
    "waste removal": "poop_scoop",
    "yard cleanup": "poop_scoop",
    "poop cleanup": "poop_scoop",
    
    # Overnight services
    "overnight": "overnight",
    "overnight care": "overnight",
    "overnight stay": "overnight",
    "overnight walk": "overnight_walk",
    "night walk": "overnight_walk",
    "late night walk": "overnight_walk",
    "overnight boarding": "overnight",
    
    # Additional services
    "pet sitting": "pet_sitting",
    "boarding": "boarding",
    "grooming": "grooming",
}


def _normalize_string(s: str) -> str:
    """Normalize a string for comparison by converting to lowercase and removing extra whitespace."""
    return re.sub(r'\s+', ' ', s.lower().strip())


def _calculate_similarity(s1: str, s2: str) -> float:
    """Calculate similarity score between two strings using multiple criteria."""
    s1_norm = _normalize_string(s1)
    s2_norm = _normalize_string(s2)
    
    if s1_norm == s2_norm:
        return 1.0
    
    # Check for exact substring matches - higher priority for longer matches
    if s1_norm in s2_norm:
        return 0.9 + (len(s1_norm) / len(s2_norm)) * 0.1
    if s2_norm in s1_norm:
        return 0.9 + (len(s2_norm) / len(s1_norm)) * 0.1
    
    # Calculate word overlap with length bonus
    words1 = set(s1_norm.split())
    words2 = set(s2_norm.split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    base_score = len(intersection) / len(union) if union else 0.0
    
    # Bonus for matching more specific terms (more words in common)
    word_match_bonus = len(intersection) / max(len(words1), len(words2)) * 0.2
    
    return min(1.0, base_score + word_match_bonus)


def get_service_code(label: str) -> Optional[str]:
    """
    Get service code for a given label with fuzzy match fallback.
    
    Args:
        label: Display label to look up
        
    Returns:
        Service code string if found, None otherwise
    """
    if not label or not isinstance(label, str):
        return None
    
    normalized_label = _normalize_string(label)
    
    # Direct lookup first
    if normalized_label in DISPLAY_TO_SERVICE_CODE:
        return DISPLAY_TO_SERVICE_CODE[normalized_label]
    
    # Fuzzy match fallback
    best_match = None
    best_score = 0.0
    min_threshold = 0.6  # Minimum similarity threshold
    
    for display_label, service_code in DISPLAY_TO_SERVICE_CODE.items():
        similarity = _calculate_similarity(normalized_label, display_label)
        if similarity > best_score and similarity >= min_threshold:
            best_score = similarity
            best_match = service_code
    
    return best_match


def get_service_display_name(code: str) -> str:
    """
    Get display name for a service code (reverse lookup).
    
    Args:
        code: Service code to look up
        
    Returns:
        Display name string, or the code itself if no display name found
    """
    if not code or not isinstance(code, str):
        return ""
    
    normalized_code = _normalize_string(code)
    
    # Find the first display label that maps to this code
    for display_label, service_code in DISPLAY_TO_SERVICE_CODE.items():
        if service_code == normalized_code:
            return display_label.title()  # Return in title case
    
    # If no display name found, return a formatted version of the code
    return code.replace('_', ' ').title()


def resolve_service_fields(label_or_code: str) -> Tuple[str, str]:
    """
    Resolve service fields from either a label or code input.
    
    Args:
        label_or_code: Either a service label or service code
        
    Returns:
        Tuple of (service_code, display_label)
    """
    if not label_or_code or not isinstance(label_or_code, str):
        return "", ""
    
    # First try to get service code (assuming input is a label)
    service_code = get_service_code(label_or_code)
    
    if service_code:
        # Found a mapping, so input was likely a label
        display_label = get_service_display_name(service_code)
        return service_code, display_label
    
    # If no mapping found, assume input is already a service code
    normalized_input = _normalize_string(label_or_code)
    display_label = get_service_display_name(normalized_input)
    
    return normalized_input, display_label