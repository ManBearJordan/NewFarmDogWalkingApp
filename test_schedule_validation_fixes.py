#!/usr/bin/env python3

"""
Test to verify schedule validation logic prevents unnecessary dialog reappearance.
This tests the specific issue mentioned in the problem statement about dialogs reappearing.
"""

from subscription_validator import is_subscription_schedule_complete, get_subscriptions_missing_schedule_data
from subscription_sync import extract_schedule_from_subscription

def test_schedule_completion_validation():
    """Test that completed schedules are properly identified"""
    
    print("=== Testing Schedule Completion Validation ===\n")
    
    # Test case 1: Complete schedule with all required fields
    complete_subscription = {
        "id": "sub_complete123",
        "metadata": {
            "schedule_days": "MON,WED,FRI",
            "schedule_start_time": "10:00",
            "schedule_end_time": "11:30",
            "schedule_location": "123 Main St, Brisbane",
            "schedule_dogs": "2",
            "schedule_notes": "Regular walking schedule",
            "service_code": "DOG_WALK"
        }
    }
    
    print("Test 1: Complete subscription")
    is_complete = is_subscription_schedule_complete(complete_subscription)
    print(f"Is complete: {is_complete}")
    assert is_complete == True, "Complete subscription should be identified as complete"
    print("✅ PASSED\n")
    
    # Test case 2: Subscription with default times (should be incomplete)
    default_times_subscription = {
        "id": "sub_default456", 
        "metadata": {
            "schedule_days": "MON,TUE",
            "schedule_start_time": "09:00",  # Default start time
            "schedule_end_time": "10:00",    # Default end time
            "schedule_location": "456 Oak Ave",
            "schedule_dogs": "1"
        }
    }
    
    print("Test 2: Subscription with default times")
    is_complete = is_subscription_schedule_complete(default_times_subscription)
    print(f"Is complete: {is_complete}")
    assert is_complete == False, "Subscription with default times should be incomplete"
    print("✅ PASSED\n")
    
    # Test case 3: Subscription missing location
    missing_location_subscription = {
        "id": "sub_missing789",
        "metadata": {
            "schedule_days": "TUE,THU",
            "schedule_start_time": "14:00",
            "schedule_end_time": "15:30",
            "schedule_dogs": "3"
            # Missing location
        }
    }
    
    print("Test 3: Subscription missing location")
    is_complete = is_subscription_schedule_complete(missing_location_subscription)
    print(f"Is complete: {is_complete}")
    assert is_complete == False, "Subscription missing location should be incomplete"
    print("✅ PASSED\n")
    
    # Test case 4: Subscription with both prefixed and non-prefixed keys
    mixed_keys_subscription = {
        "id": "sub_mixed000",
        "metadata": {
            "days": "MON,WED,FRI",          # Non-prefixed
            "start_time": "08:30",          # Non-prefixed
            "end_time": "09:45",            # Non-prefixed  
            "schedule_location": "789 Pine St",  # Prefixed
            "dogs": "1"                     # Non-prefixed
        }
    }
    
    print("Test 4: Subscription with mixed key formats")
    is_complete = is_subscription_schedule_complete(mixed_keys_subscription)
    print(f"Is complete: {is_complete}")
    assert is_complete == True, "Subscription with mixed keys should be complete"
    print("✅ PASSED\n")


def test_missing_data_detection():
    """Test that missing data detection works correctly with the new logic"""
    
    print("=== Testing Missing Data Detection ===\n")
    
    # Test case 1: Complete subscription should not appear in missing data
    complete_subscription = {
        "id": "sub_complete123",
        "metadata": {
            "schedule_days": "MON,WED,FRI",
            "schedule_start_time": "10:00",
            "schedule_end_time": "11:30",
            "schedule_location": "123 Main St, Brisbane",
            "schedule_dogs": "2",
            "service_code": "DOG_WALK"
        }
    }
    
    subscriptions = [complete_subscription]
    missing_data_subs = get_subscriptions_missing_schedule_data(subscriptions)
    
    print("Test 1: Complete subscription should not be flagged as missing data")
    print(f"Missing data subscriptions found: {len(missing_data_subs)}")
    assert len(missing_data_subs) == 0, "Complete subscription should not be in missing data list"
    print("✅ PASSED\n")
    
    # Test case 2: Incomplete subscription should appear in missing data
    incomplete_subscription = {
        "id": "sub_incomplete456",
        "metadata": {
            "schedule_days": "MON,TUE",
            # Missing start_time, end_time, location, dogs
        }
    }
    
    subscriptions = [incomplete_subscription]
    missing_data_subs = get_subscriptions_missing_schedule_data(subscriptions)
    
    print("Test 2: Incomplete subscription should be flagged as missing data")
    print(f"Missing data subscriptions found: {len(missing_data_subs)}")
    assert len(missing_data_subs) == 1, "Incomplete subscription should be in missing data list"
    
    missing_fields = missing_data_subs[0].get("missing_fields", [])
    print(f"Missing fields: {missing_fields}")
    
    expected_missing = {"start_time", "end_time", "location", "dogs", "service_code"}
    actual_missing = set(missing_fields)
    
    assert expected_missing.issubset(actual_missing), f"Expected missing fields {expected_missing}, got {actual_missing}"
    print("✅ PASSED\n")


def test_schedule_extraction_multiple_key_formats():
    """Test that schedule extraction works with multiple key formats"""
    
    print("=== Testing Schedule Extraction Key Format Support ===\n")
    
    # Test prefixed keys
    prefixed_subscription = {
        "metadata": {
            "schedule_days": "MON,WED,FRI",
            "schedule_start_time": "10:00",
            "schedule_end_time": "11:30",
            "schedule_location": "123 Main St",
            "schedule_dogs": "2",
            "schedule_notes": "Test notes"
        }
    }
    
    schedule = extract_schedule_from_subscription(prefixed_subscription)
    print("Test 1: Prefixed keys extraction")
    print(f"Days: {schedule['days']}")
    print(f"Start time: {schedule['start_time']}")
    print(f"End time: {schedule['end_time']}")
    print(f"Location: {schedule['location']}")
    print(f"Dogs: {schedule['dogs']}")
    
    assert schedule["days"] == "MON,WED,FRI", "Failed to extract prefixed days"
    assert schedule["start_time"] == "10:00", "Failed to extract prefixed start_time"
    assert schedule["end_time"] == "11:30", "Failed to extract prefixed end_time"
    assert schedule["location"] == "123 Main St", "Failed to extract prefixed location"
    assert schedule["dogs"] == 2, "Failed to extract prefixed dogs"
    print("✅ PASSED\n")
    
    # Test non-prefixed keys
    non_prefixed_subscription = {
        "metadata": {
            "days": "TUE,THU",
            "start_time": "14:00",
            "end_time": "15:30",
            "location": "456 Oak Ave",
            "dogs": "1",
            "notes": "Different notes"
        }
    }
    
    schedule = extract_schedule_from_subscription(non_prefixed_subscription)
    print("Test 2: Non-prefixed keys extraction")
    print(f"Days: {schedule['days']}")
    print(f"Start time: {schedule['start_time']}")
    print(f"End time: {schedule['end_time']}")
    print(f"Location: {schedule['location']}")
    print(f"Dogs: {schedule['dogs']}")
    
    assert schedule["days"] == "TUE,THU", "Failed to extract non-prefixed days"
    assert schedule["start_time"] == "14:00", "Failed to extract non-prefixed start_time"
    assert schedule["end_time"] == "15:30", "Failed to extract non-prefixed end_time"
    assert schedule["location"] == "456 Oak Ave", "Failed to extract non-prefixed location"
    assert schedule["dogs"] == 1, "Failed to extract non-prefixed dogs"
    print("✅ PASSED\n")


if __name__ == '__main__':
    try:
        test_schedule_completion_validation()
        test_missing_data_detection()
        test_schedule_extraction_multiple_key_formats()
        
        print("🚀 All schedule validation tests completed successfully!")
        print("✅ Schedule completion validation is working correctly")
        print("✅ Missing data detection is working correctly") 
        print("✅ Multiple key format support is working correctly")
        print("\n🎯 This validates that dialogs will NOT reappear for completed schedules!")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        exit(1)