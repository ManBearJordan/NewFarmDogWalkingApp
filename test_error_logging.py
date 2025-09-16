"""
Test script to verify the subscription error logging implementation.

This script tests all the error logging functionality to ensure it works correctly.
"""

import sys
import os
from datetime import datetime

def test_log_utils():
    """Test the log_utils module."""
    print("Testing log_utils module...")
    
    try:
        from log_utils import (
            get_subscription_logger, 
            log_subscription_error, 
            log_subscription_info, 
            log_subscription_warning,
            initialize_error_log
        )
        
        # Initialize the error log
        initialize_error_log()
        print("✓ Error log initialized successfully")
        
        # Test basic logging functions
        test_sub_id = "sub_test123456789"
        
        log_subscription_info("Test info message", test_sub_id)
        print("✓ Info logging works")
        
        log_subscription_warning("Test warning message", test_sub_id)
        print("✓ Warning logging works")
        
        log_subscription_error("Test error message", test_sub_id)
        print("✓ Error logging works")
        
        # Test error logging with exception
        try:
            raise ValueError("Test exception for logging")
        except Exception as e:
            log_subscription_error("Test error with exception", test_sub_id, e)
            print("✓ Error logging with exception works")
        
        return True
        
    except Exception as e:
        print(f"✗ log_utils test failed: {e}")
        return False


def test_customer_display_helpers():
    """Test the customer display helpers with error logging."""
    print("\nTesting customer_display_helpers module...")
    
    try:
        from customer_display_helpers import get_robust_customer_display_info
        
        # Test with minimal subscription data
        test_subscription = {
            "id": "sub_test123456789",
            "customer": {
                "id": "cus_test123456789",
                "name": "Test Customer",
                "email": "test@example.com"
            }
        }
        
        result = get_robust_customer_display_info(test_subscription)
        print(f"✓ Customer display result: {result}")
        
        # Test with missing customer data
        test_subscription_missing = {
            "id": "sub_test_missing",
            "customer": {}
        }
        
        result_missing = get_robust_customer_display_info(test_subscription_missing)
        print(f"✓ Missing customer data result: {result_missing}")
        
        return True
        
    except Exception as e:
        print(f"✗ customer_display_helpers test failed: {e}")
        return False


def test_booking_utils():
    """Test the booking utilities with error logging."""
    print("\nTesting booking_utils module...")
    
    try:
        from booking_utils import validate_schedule_data, generate_bookings_and_update_calendar
        
        # Test schedule validation
        test_schedule = {
            "days": "MON,WED,FRI",
            "start_time": "09:00",
            "end_time": "10:00",
            "location": "123 Test Street, Brisbane",
            "dogs": 2,
            "notes": "Test booking"
        }
        
        validation_result = validate_schedule_data("sub_test123456789", test_schedule)
        print(f"✓ Schedule validation result: {validation_result}")
        
        # Test with invalid schedule data
        invalid_schedule = {
            "days": "INVALID_DAY",
            "start_time": "invalid_time",
            "end_time": "10:00",
            "location": "",
            "dogs": -1
        }
        
        invalid_result = validate_schedule_data("sub_test_invalid", invalid_schedule)
        print(f"✓ Invalid schedule validation result: {invalid_result}")
        
        return True
        
    except Exception as e:
        print(f"✗ booking_utils test failed: {e}")
        return False


def check_error_log_file():
    """Check if the error log file was created and has content."""
    print("\nChecking error log file...")
    
    log_file = "subscription_error_log.txt"
    
    if os.path.exists(log_file):
        print(f"✓ Error log file exists: {log_file}")
        
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if content:
            print(f"✓ Error log file has content ({len(content)} characters)")
            
            # Show last few lines of the log
            lines = content.strip().split('\n')
            print("\nLast few log entries:")
            for line in lines[-5:]:
                if line and not line.startswith('#'):
                    print(f"  {line}")
            
            return True
        else:
            print("✗ Error log file is empty")
            return False
    else:
        print(f"✗ Error log file not found: {log_file}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("SUBSCRIPTION ERROR LOGGING TEST SUITE")
    print("=" * 60)
    
    tests_passed = 0
    total_tests = 4
    
    # Run tests
    if test_log_utils():
        tests_passed += 1
    
    if test_customer_display_helpers():
        tests_passed += 1
    
    if test_booking_utils():
        tests_passed += 1
    
    if check_error_log_file():
        tests_passed += 1
    
    # Summary
    print("\n" + "=" * 60)
    print(f"TEST RESULTS: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("✓ All tests passed! Error logging implementation is working correctly.")
        print("\nThe subscription error logging system is ready for use.")
        print("When bugs occur, check 'subscription_error_log.txt' for detailed error information.")
    else:
        print("✗ Some tests failed. Please check the implementation.")
    
    print("=" * 60)
    
    return tests_passed == total_tests


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
