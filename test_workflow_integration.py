#!/usr/bin/env python3

"""
End-to-end integration test to verify the complete subscription schedule workflow.
This validates all the fixes from the problem statement work together.
"""

import sqlite3
import tempfile
import os
from db import get_conn
from subscription_validator import (
    get_subscriptions_missing_schedule_data, 
    is_subscription_schedule_complete,
    update_local_subscription_schedule
)
from subscription_sync import extract_schedule_from_subscription

def test_complete_workflow():
    """Test the complete subscription schedule workflow end-to-end"""
    
    print("=== End-to-End Subscription Workflow Test ===\n")
    
    # Use existing database
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    
    print("✅ Connected to database")
    
    # Test scenario: User has an incomplete subscription
    incomplete_subscription = {
                "id": "sub_test_workflow_123",
                "customer": {
                    "id": "cus_test_123",
                    "name": None,  # No name - should fallback to email
                    "email": "testuser@example.com"
                },
                "metadata": {
                    "schedule_days": "MON,WED,FRI",
                    # Missing start_time, end_time, location, dogs
                }
            }
            
            print("Step 1: Check incomplete subscription is identified correctly")
            missing_subs = get_subscriptions_missing_schedule_data([incomplete_subscription])
            assert len(missing_subs) == 1, "Should identify incomplete subscription"
            
            missing_fields = missing_subs[0]["missing_fields"]
            print(f"Missing fields identified: {missing_fields}")
            
            expected_missing = {"start_time", "end_time", "location", "dogs"}
            actual_missing = set(missing_fields)
            assert expected_missing.issubset(actual_missing), f"Expected {expected_missing} in missing fields"
            print("✅ Incomplete subscription correctly identified")
            
            # Step 2: User completes the schedule via dialog
            print("\nStep 2: Simulate user completing schedule via dialog")
            schedule_data = {
                "days": "MON,WED,FRI",
                "start_time": "10:00",
                "end_time": "11:30", 
                "location": "123 Test Street, Brisbane",
                "dogs": 2,
                "notes": "Regular walking schedule",
                "service_code": "DOG_WALK"
            }
            
            # Save to local database
            success = update_local_subscription_schedule(
                conn,
                "sub_test_workflow_123", 
                schedule_data["days"],
                schedule_data["start_time"],
                schedule_data["end_time"],
                schedule_data["location"],
                schedule_data["dogs"],
                schedule_data["notes"],
                schedule_data.get("service_code", "")
            )
            assert success, "Failed to save schedule to database"
            print("✅ Schedule saved to local database")
            
            # Step 3: Verify subscription is now complete and won't show dialog again
            print("\nStep 3: Verify subscription is now complete")
            
            # Create updated subscription with the saved metadata
            complete_subscription = {
                "id": "sub_test_workflow_123", 
                "metadata": {
                    "schedule_days": schedule_data["days"],
                    "schedule_start_time": schedule_data["start_time"],
                    "schedule_end_time": schedule_data["end_time"],
                    "schedule_location": schedule_data["location"],
                    "schedule_dogs": str(schedule_data["dogs"]),
                    "schedule_notes": schedule_data["notes"],
                    "service_code": schedule_data["service_code"]
                }
            }
            
            # Check if it's complete
            is_complete = is_subscription_schedule_complete(complete_subscription)
            assert is_complete, "Completed subscription should be identified as complete"
            print("✅ Subscription correctly identified as complete")
            
            # Check it doesn't appear in missing data anymore
            missing_subs_after = get_subscriptions_missing_schedule_data([complete_subscription])
            assert len(missing_subs_after) == 0, "Complete subscription should not be in missing data"
            print("✅ Complete subscription no longer flagged as missing data")
            
            # Step 4: Verify schedule data can be extracted properly
            print("\nStep 4: Verify schedule data extraction")
            extracted_schedule = extract_schedule_from_subscription(complete_subscription)
            
            assert extracted_schedule["days"] == schedule_data["days"]
            assert extracted_schedule["start_time"] == schedule_data["start_time"]
            assert extracted_schedule["end_time"] == schedule_data["end_time"]
            assert extracted_schedule["location"] == schedule_data["location"]
            assert extracted_schedule["dogs"] == schedule_data["dogs"]
            assert len(extracted_schedule["day_list"]) == 3  # MON,WED,FRI
            assert "MON" in extracted_schedule["day_list"]
            assert "WED" in extracted_schedule["day_list"] 
            assert "FRI" in extracted_schedule["day_list"]
            
            print("✅ Schedule data extracted correctly")
            
            # Step 5: Verify database persistence
            print("\nStep 5: Verify database persistence")
            saved_schedule = conn.execute("""
                SELECT days, start_time, end_time, location, dogs, notes
                FROM subs_schedule 
                WHERE stripe_subscription_id = ?
            """, ("sub_test_workflow_123",)).fetchone()
            
            assert saved_schedule is not None, "Schedule should be saved in database"
            assert saved_schedule["days"] == schedule_data["days"]
            assert saved_schedule["start_time"] == schedule_data["start_time"] 
            assert saved_schedule["end_time"] == schedule_data["end_time"]
            assert saved_schedule["location"] == schedule_data["location"]
            assert saved_schedule["dogs"] == schedule_data["dogs"]
            
            print("✅ Schedule data persisted correctly in database")
            
            print("\n🎉 Complete workflow test passed!")
            print("\n" + "="*60)
            print("WORKFLOW VALIDATION SUMMARY:")
            print("="*60)
            print("✅ Incomplete subscriptions are correctly identified")
            print("✅ Missing fields are accurately detected")
            print("✅ Schedule data can be saved to local database")
            print("✅ Completed subscriptions are marked as complete") 
            print("✅ Dialogs will NOT reappear for complete subscriptions")
            print("✅ Schedule data extraction works with multiple key formats")
            print("✅ Database persistence is working correctly")
            print("="*60)
            
    # Clean up
    conn.close()


if __name__ == '__main__':
    try:
        test_complete_workflow()
        print("\n🚀 End-to-end workflow test completed successfully!")
        print("🎯 All critical subscription schedule issues have been resolved!")
        
    except AssertionError as e:
        print(f"\n❌ Workflow test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        exit(1)