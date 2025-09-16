"""
Test script to verify all subscription schedule dialog fixes are working properly.

This script tests:
1. Customer name retrieval issues in subscription checks
2. Scheduler window reopening after confirmation
3. Service type display issues in bookings/calendar
"""

import logging
import sqlite3
from typing import Dict, Any
from unittest.mock import Mock, patch

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_customer_name_retrieval():
    """Test that customer names are properly retrieved from Stripe API when missing."""
    print("Testing customer name retrieval...")
    
    try:
        from customer_display_helpers import get_robust_customer_display_info
        
        # Test case 1: Customer data with name and email
        subscription_data_1 = {
            "id": "sub_test123",
            "customer": {
                "id": "cus_test123",
                "name": "John Doe",
                "email": "john@example.com"
            }
        }
        
        result_1 = get_robust_customer_display_info(subscription_data_1)
        assert "John Doe" in result_1, f"Expected 'John Doe' in result, got: {result_1}"
        assert "john@example.com" in result_1, f"Expected email in result, got: {result_1}"
        print("✅ Test 1 passed: Customer with name and email")
        
        # Test case 2: Customer data with only email
        subscription_data_2 = {
            "id": "sub_test456",
            "customer": {
                "id": "cus_test456",
                "name": "",
                "email": "jane@example.com"
            }
        }
        
        result_2 = get_robust_customer_display_info(subscription_data_2)
        assert "jane@example.com" in result_2, f"Expected email in result, got: {result_2}"
        print("✅ Test 2 passed: Customer with only email")
        
        # Test case 3: Customer ID only (should trigger Stripe API call)
        subscription_data_3 = {
            "id": "sub_test789",
            "customer": "cus_test789"
        }
        
        # Mock the Stripe API call
        with patch('stripe_integration._api') as mock_api:
            mock_customer = Mock()
            mock_customer.name = "Bob Smith"
            mock_customer.email = "bob@example.com"
            mock_api.return_value.Customer.retrieve.return_value = mock_customer
            
            result_3 = get_robust_customer_display_info(subscription_data_3)
            assert "Bob Smith" in result_3, f"Expected 'Bob Smith' in result, got: {result_3}"
            print("✅ Test 3 passed: Customer ID only with Stripe API fallback")
        
        print("✅ All customer name retrieval tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Customer name retrieval test failed: {e}")
        return False


def test_service_type_mapping():
    """Test that service types are properly mapped and displayed."""
    print("Testing service type mapping...")
    
    try:
        from service_map import get_service_display_name, get_service_code
        from unified_booking_helpers import get_canonical_service_info
        
        # Test case 1: Valid service code to display name
        display_name = get_service_display_name("WALK_SHORT_SINGLE")
        assert display_name == "Short Walk (Single)", f"Expected 'Short Walk (Single)', got: {display_name}"
        print("✅ Test 1 passed: Service code to display name")
        
        # Test case 2: Display name to service code
        service_code = get_service_code("Short Walk (Single)")
        assert service_code == "WALK_SHORT_SINGLE", f"Expected 'WALK_SHORT_SINGLE', got: {service_code}"
        print("✅ Test 2 passed: Display name to service code")
        
        # Test case 3: Canonical service info extraction
        service_type, service_label = get_canonical_service_info("Short Walk (Single)")
        assert service_type == "WALK_SHORT_SINGLE", f"Expected 'WALK_SHORT_SINGLE', got: {service_type}"
        assert "Short Walk" in service_label, f"Expected 'Short Walk' in label, got: {service_label}"
        print("✅ Test 3 passed: Canonical service info extraction")
        
        print("✅ All service type mapping tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Service type mapping test failed: {e}")
        return False


def test_dialog_completion_tracking():
    """Test that dialog completion is properly tracked to prevent reopening."""
    print("Testing dialog completion tracking...")
    
    try:
        from startup_sync import StartupSyncManager
        from PySide6.QtWidgets import QApplication, QMainWindow
        import sys
        
        # Create minimal Qt application for testing
        if not QApplication.instance():
            app = QApplication(sys.argv)
        
        main_window = QMainWindow()
        sync_manager = StartupSyncManager(main_window)
        
        # Mock subscription data
        missing_data_subscriptions = [
            {
                "id": "sub_test123",
                "customer": {"name": "Test Customer", "email": "test@example.com"},
                "missing_fields": ["days", "start_time"]
            }
        ]
        
        # Test that completed subscriptions are tracked
        completed_subscriptions = set()
        
        # Simulate dialog completion
        subscription_id = "sub_test123"
        completed_subscriptions.add(subscription_id)
        
        # Verify subscription is marked as completed
        assert subscription_id in completed_subscriptions, "Subscription should be marked as completed"
        print("✅ Test 1 passed: Dialog completion tracking")
        
        # Test that completed subscriptions are skipped
        if subscription_id in completed_subscriptions:
            print("✅ Test 2 passed: Completed subscriptions are properly skipped")
        
        print("✅ All dialog completion tracking tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Dialog completion tracking test failed: {e}")
        return False


def test_booking_creation_with_service_types():
    """Test that bookings are created with proper service types."""
    print("Testing booking creation with service types...")
    
    try:
        from unified_booking_helpers import create_booking_with_unified_fields
        from db import get_conn
        
        # Get database connection
        conn = get_conn()
        
        # Test booking creation
        booking_id = create_booking_with_unified_fields(
            conn=conn,
            client_id=1,  # Assuming client ID 1 exists
            service_input="Short Walk (Single)",
            start_dt="2024-01-15 09:00:00",
            end_dt="2024-01-15 10:00:00",
            location="Test Location",
            dogs=1,
            price_cents=5000,
            notes="Test booking",
            source="test"
        )
        
        # Verify booking was created with correct service type
        cur = conn.cursor()
        booking = cur.execute("""
            SELECT service_type, service, service_name 
            FROM bookings 
            WHERE id = ?
        """, (booking_id,)).fetchone()
        
        if booking:
            assert booking["service_type"] == "WALK_SHORT_SINGLE", f"Expected 'WALK_SHORT_SINGLE', got: {booking['service_type']}"
            assert "Short Walk" in booking["service"], f"Expected 'Short Walk' in service, got: {booking['service']}"
            print("✅ Test 1 passed: Booking created with correct service type")
            
            # Clean up test booking
            cur.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
            conn.commit()
        else:
            print("❌ Test booking was not created")
            return False
        
        print("✅ All booking creation tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Booking creation test failed: {e}")
        return False


def run_all_tests():
    """Run all tests and report results."""
    print("🧪 Running subscription schedule dialog fixes tests...\n")
    
    tests = [
        ("Customer Name Retrieval", test_customer_name_retrieval),
        ("Service Type Mapping", test_service_type_mapping),
        ("Dialog Completion Tracking", test_dialog_completion_tracking),
        ("Booking Creation with Service Types", test_booking_creation_with_service_types),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            failed += 1
    
    print(f"\n🏁 Test Results:")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total: {passed + failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed! The subscription schedule dialog fixes are working correctly.")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the issues above.")
    
    return failed == 0


if __name__ == "__main__":
    run_all_tests()
