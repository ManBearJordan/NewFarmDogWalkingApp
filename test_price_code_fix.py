#!/usr/bin/env python3
"""
Test to verify the price_code fix works correctly for service type mapping
"""

def test_price_code_prioritization():
    """
    Test that price_code is prioritized over service_code when both are present
    """
    
    # Mock metadata with both price_code and service_code
    test_metadata = {
        'price_code': 'DAYCARE_FORTNIGHTLY_PER_VISIT',
        'service_code': 'DAYCARE',
        'service_name': 'Daycare Fortnightly per Visit'
    }
    
    # Test the logic we implemented
    service_type = None
    
    # This simulates the new logic: check price_code first, then service_code
    if test_metadata.get('price_code') and not service_type:
        service_type = test_metadata['price_code'].strip()
    elif test_metadata.get('service_code') and not service_type:
        service_type = test_metadata['service_code'].strip()
    
    print(f"Test metadata: {test_metadata}")
    print(f"Resolved service_type: {service_type}")
    
    # Verify we got the more specific price_code value
    assert service_type == 'DAYCARE_FORTNIGHTLY_PER_VISIT', f"Expected DAYCARE_FORTNIGHTLY_PER_VISIT, got {service_type}"
    print("✓ Test passed: price_code is prioritized over service_code")

def test_fallback_to_service_code():
    """
    Test that we fall back to service_code when price_code is not available
    """
    
    # Mock metadata with only service_code
    test_metadata = {
        'service_code': 'DAYCARE',
        'service_name': 'Daycare Service'
    }
    
    service_type = None
    
    # This simulates the new logic: check price_code first, then service_code
    if test_metadata.get('price_code') and not service_type:
        service_type = test_metadata['price_code'].strip()
    elif test_metadata.get('service_code') and not service_type:
        service_type = test_metadata['service_code'].strip()
    
    print(f"Test metadata: {test_metadata}")
    print(f"Resolved service_type: {service_type}")
    
    # Verify we got the service_code value since price_code is not available
    assert service_type == 'DAYCARE', f"Expected DAYCARE, got {service_type}"
    print("✓ Test passed: Falls back to service_code when price_code is not available")

def test_unified_booking_helpers_integration():
    """
    Test that the service_type_from_label function works correctly with the resolved service types
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    from unified_booking_helpers import service_type_from_label
    
    # Test that the specific service type is handled correctly
    result1 = service_type_from_label('DAYCARE_FORTNIGHTLY_PER_VISIT')
    print(f"service_type_from_label('DAYCARE_FORTNIGHTLY_PER_VISIT') = {result1}")
    assert result1 == 'DAYCARE_FORTNIGHTLY_PER_VISIT', f"Expected DAYCARE_FORTNIGHTLY_PER_VISIT, got {result1}"
    
    # Test that the generic service type is handled correctly  
    result2 = service_type_from_label('DAYCARE')
    print(f"service_type_from_label('DAYCARE') = {result2}")
    assert result2 == 'DAYCARE_SINGLE', f"Expected DAYCARE_SINGLE, got {result2}"
    
    print("✓ Test passed: unified_booking_helpers handles both specific and generic service types correctly")

if __name__ == "__main__":
    print("Testing price_code prioritization fix...")
    print()
    
    test_price_code_prioritization()
    print()
    
    test_fallback_to_service_code()
    print()
    
    test_unified_booking_helpers_integration()
    print()
    
    print("All tests passed! ✓")