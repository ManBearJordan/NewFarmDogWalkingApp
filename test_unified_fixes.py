#!/usr/bin/env python3
"""
Test script to verify the unified booking helper functions work correctly.
This tests the minimal dev changes implemented to fix the issues in DEBUGGING_REPORT.md
"""

import sqlite3
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unified_booking_helpers import (
    resolve_client_id, 
    service_type_from_label, 
    get_canonical_service_info,
    create_booking_with_unified_fields,
    purge_future_subscription_bookings,
    rebuild_subscription_bookings
)
from db import get_conn

def test_service_type_derivation():
    """Test the unified service type derivation function"""
    print("Testing service_type_from_label()...")
    
    test_cases = [
        # Test cases from the debugging report
        ("Home Visit – 30m (1×/day)", "HOME_VISIT_30M_SINGLE"),
        ("Poop Scoop – One-time", "SCOOP_SINGLE"),
        ("Short Walk", "WALK_SHORT_SINGLE"),
        ("Long Walk (Pack)", "WALK_LONG_PACKS"),
        ("Doggy Daycare (per day)", "DAYCARE_SINGLE"),
        ("Daycare (Weekly / per visit)", "DAYCARE_WEEKLY_PER_VISIT"),
        ("Pick up / Drop off", "PICKUP_DROPOFF_SINGLE"),
        
        # Test Unicode normalization
        ("Home Visit – 30m (2×/day)", "HOME_VISIT_30M_2X_SINGLE"),
        ("Walk × Short", "WALK_SHORT_SINGLE"),
        
        # Test edge cases
        ("", "WALK_GENERAL"),
        ("Subscription", "WALK_GENERAL"),
        ("Some Random Service", "SOME_RANDOM_SERVICE"),
        
        # Test overnight services
        ("Overnight Care", "OVERNIGHT_SINGLE"),
        ("Pet Sitting", "PET_SITTING_SINGLE"),
        ("Grooming & Bath", "GROOMING_SINGLE"),
    ]
    
    passed = 0
    failed = 0
    
    for input_label, expected in test_cases:
        result = service_type_from_label(input_label)
        if result == expected:
            print(f"✓ '{input_label}' → '{result}'")
            passed += 1
        else:
            print(f"✗ '{input_label}' → '{result}' (expected '{expected}')")
            failed += 1
    
    print(f"\nService type derivation: {passed} passed, {failed} failed")
    return failed == 0

def test_client_resolution():
    """Test the unified client resolution function"""
    print("\nTesting resolve_client_id()...")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Create a test client
    cur.execute("""
        INSERT OR REPLACE INTO clients (id, name, email, stripe_customer_id)
        VALUES (9999, 'Test Client', 'test@example.com', 'cus_test123')
    """)
    conn.commit()
    
    # Test resolving by stripe_customer_id
    client_id = resolve_client_id(conn, 'cus_test123')
    if client_id == 9999:
        print("✓ Resolved client by stripe_customer_id")
        success1 = True
    else:
        print(f"✗ Failed to resolve client by stripe_customer_id: got {client_id}")
        success1 = False
    
    # Test with invalid customer ID
    client_id = resolve_client_id(conn, 'cus_nonexistent')
    if client_id is None:
        print("✓ Correctly returned None for nonexistent customer")
        success2 = True
    else:
        print(f"✗ Should have returned None for nonexistent customer: got {client_id}")
        success2 = False
    
    # Test with invalid format
    client_id = resolve_client_id(conn, 'invalid_format')
    if client_id is None:
        print("✓ Correctly returned None for invalid format")
        success3 = True
    else:
        print(f"✗ Should have returned None for invalid format: got {client_id}")
        success3 = False
    
    # Clean up
    cur.execute("DELETE FROM clients WHERE id = 9999")
    conn.commit()
    conn.close()
    
    return success1 and success2 and success3

def test_canonical_service_info():
    """Test the get_canonical_service_info function"""
    print("\nTesting get_canonical_service_info()...")
    
    test_cases = [
        ("Short Walk", ("WALK_SHORT_SINGLE", "Short Walk")),
        ("Subscription", ("WALK_GENERAL", "Dog Walk")),  # Should replace generic labels
        ("", ("WALK_GENERAL", "Dog Walk")),
        ("Home Visit – 30m (1×/day)", ("HOME_VISIT_30M_SINGLE", "Home Visit – 30m (1×/day)")),
    ]
    
    passed = 0
    failed = 0
    
    for input_label, (expected_type, expected_label) in test_cases:
        service_type, service_label = get_canonical_service_info(input_label)
        if service_type == expected_type and service_label == expected_label:
            print(f"✓ '{input_label}' → ('{service_type}', '{service_label}')")
            passed += 1
        else:
            print(f"✗ '{input_label}' → ('{service_type}', '{service_label}') expected ('{expected_type}', '{expected_label}')")
            failed += 1
    
    print(f"\nCanonical service info: {passed} passed, {failed} failed")
    return failed == 0

def test_unified_booking_creation():
    """Test the unified booking creation function"""
    print("\nTesting create_booking_with_unified_fields()...")
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Create a test client
        cur.execute("""
            INSERT OR REPLACE INTO clients (id, name, email)
            VALUES (9998, 'Test Booking Client', 'testbooking@example.com')
        """)
        conn.commit()
        
        # Create a test booking
        booking_id = create_booking_with_unified_fields(
            conn, 9998, "Short Walk", "2025-09-16 10:00:00", "2025-09-16 11:00:00",
            "Test Location", 2, 5000, "Test booking", "price_test123", "manual"
        )
        
        # Verify the booking was created with correct fields
        booking = cur.execute("""
            SELECT service_type, service, service_name, stripe_price_id, source, location, dogs
            FROM bookings WHERE id = ?
        """, (booking_id,)).fetchone()
        
        if booking:
            expected_service_type = "WALK_SHORT_SINGLE"
            expected_service_label = "Short Walk"
            
            success = (
                booking["service_type"] == expected_service_type and
                booking["service"] == expected_service_label and
                booking["service_name"] == expected_service_label and
                booking["stripe_price_id"] == "price_test123" and
                booking["source"] == "manual" and
                booking["location"] == "Test Location" and
                booking["dogs"] == 2
            )
            
            if success:
                print(f"✓ Created booking {booking_id} with unified fields")
                print(f"  service_type: {booking['service_type']}")
                print(f"  service: {booking['service']}")
                print(f"  stripe_price_id: {booking['stripe_price_id']}")
                print(f"  source: {booking['source']}")
            else:
                print(f"✗ Booking fields incorrect:")
                print(f"  service_type: {booking['service_type']} (expected {expected_service_type})")
                print(f"  service: {booking['service']} (expected {expected_service_label})")
                print(f"  stripe_price_id: {booking['stripe_price_id']}")
                print(f"  source: {booking['source']}")
        else:
            print("✗ Booking was not created")
            success = False
        
        # Clean up
        cur.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        cur.execute("DELETE FROM clients WHERE id = 9998")
        conn.commit()
        
    except Exception as e:
        print(f"✗ Error testing unified booking creation: {e}")
        success = False
    finally:
        conn.close()
    
    return success

def test_purge_functionality():
    """Test the purge future subscription bookings function"""
    print("\nTesting purge_future_subscription_bookings()...")
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Create test data
        cur.execute("""
            INSERT OR REPLACE INTO clients (id, name, email)
            VALUES (9997, 'Test Purge Client', 'testpurge@example.com')
        """)
        
        # Create some future subscription bookings
        cur.execute("""
            INSERT INTO bookings (client_id, service_type, service, start_dt, end_dt, source, created_from_sub_id)
            VALUES 
            (9997, 'WALK_SHORT_SINGLE', 'Short Walk', '2025-12-01 10:00:00', '2025-12-01 11:00:00', 'subscription', 'sub_test123'),
            (9997, 'WALK_SHORT_SINGLE', 'Short Walk', '2025-12-02 10:00:00', '2025-12-02 11:00:00', 'subscription', 'sub_test123'),
            (9997, 'WALK_SHORT_SINGLE', 'Short Walk', '2025-12-03 10:00:00', '2025-12-03 11:00:00', 'subscription', 'sub_other456')
        """)
        conn.commit()
        
        # Count bookings before purge
        count_before = cur.execute("""
            SELECT COUNT(*) FROM bookings 
            WHERE source = 'subscription' AND created_from_sub_id = 'sub_test123'
        """).fetchone()[0]
        
        # Purge bookings for sub_test123
        purge_future_subscription_bookings(conn, 'sub_test123')
        
        # Count bookings after purge
        count_after = cur.execute("""
            SELECT COUNT(*) FROM bookings 
            WHERE source = 'subscription' AND created_from_sub_id = 'sub_test123'
        """).fetchone()[0]
        
        # Count bookings for other subscription (should be unchanged)
        count_other = cur.execute("""
            SELECT COUNT(*) FROM bookings 
            WHERE source = 'subscription' AND created_from_sub_id = 'sub_other456'
        """).fetchone()[0]
        
        success = (count_before == 2 and count_after == 0 and count_other == 1)
        
        if success:
            print(f"✓ Purged {count_before} bookings for sub_test123, left {count_other} for sub_other456")
        else:
            print(f"✗ Purge failed: before={count_before}, after={count_after}, other={count_other}")
        
        # Clean up
        cur.execute("DELETE FROM bookings WHERE client_id = 9997")
        cur.execute("DELETE FROM clients WHERE id = 9997")
        conn.commit()
        
    except Exception as e:
        print(f"✗ Error testing purge functionality: {e}")
        success = False
    finally:
        conn.close()
    
    return success

def run_all_tests():
    """Run all tests and report results"""
    print("=" * 60)
    print("TESTING UNIFIED BOOKING HELPER FUNCTIONS")
    print("=" * 60)
    
    tests = [
        ("Service Type Derivation", test_service_type_derivation),
        ("Client Resolution", test_client_resolution),
        ("Canonical Service Info", test_canonical_service_info),
        ("Unified Booking Creation", test_unified_booking_creation),
        ("Purge Functionality", test_purge_functionality),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nOverall: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n🎉 All tests passed! The unified booking helpers are working correctly.")
        return True
    else:
        print(f"\n❌ {failed} test(s) failed. Please review the implementation.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
