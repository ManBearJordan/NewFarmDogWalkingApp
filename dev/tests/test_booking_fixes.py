#!/usr/bin/env python3
"""
Test script to verify that booking creation and import fixes are working correctly.

This script tests:
1. That bookings are created with proper client_id, service_type, and service labels
2. That import functions handle missing data correctly
3. That legacy data has been cleaned up
"""

import sqlite3
import sys
import os
from datetime import datetime

# Add the current directory to Python path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import get_conn, add_or_upsert_booking

def test_booking_creation():
    """Test that booking creation sets proper values"""
    print("=== TESTING BOOKING CREATION ===")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get a test client
    client_row = cur.execute("SELECT id FROM clients LIMIT 1").fetchone()
    if not client_row:
        print("No clients found - creating test client")
        cur.execute("INSERT INTO clients (name, email) VALUES (?, ?)", ("Test Client", "test@example.com"))
        conn.commit()
        client_id = cur.lastrowid
    else:
        client_id = client_row["id"]
    
    # Test 1: Create booking with proper service details
    print("\nTest 1: Creating booking with proper service details")
    booking_id = add_or_upsert_booking(
        conn, client_id, "Short Walk", "WALK_SHORT_SINGLE",
        "2025-09-16 09:00:00", "2025-09-16 10:00:00", 
        "Test Location", 1, 5500, "Test booking"
    )
    
    # Verify the booking was created correctly
    booking = cur.execute("""
        SELECT client_id, service, service_type, service_name, location, dogs, price_cents, notes
        FROM bookings WHERE id = ?
    """, (booking_id,)).fetchone()
    
    if booking:
        print(f"✅ Booking {booking_id} created successfully:")
        print(f"   Client ID: {booking['client_id']}")
        print(f"   Service: '{booking['service']}'")
        print(f"   Service Type: '{booking['service_type']}'")
        print(f"   Service Name: '{booking['service_name']}'")
        print(f"   Location: '{booking['location']}'")
        print(f"   Dogs: {booking['dogs']}")
        print(f"   Price: {booking['price_cents']} cents")
        
        # Validate that no fields are empty or generic
        issues = []
        if not booking['client_id']:
            issues.append("Missing client_id")
        if not booking['service'] or booking['service'].lower() in ['subscription', 'service', 'none']:
            issues.append(f"Invalid service: '{booking['service']}'")
        if not booking['service_type'] or booking['service_type'].lower() in ['subscription', 'service', 'none']:
            issues.append(f"Invalid service_type: '{booking['service_type']}'")
        
        if issues:
            print(f"❌ Issues found: {', '.join(issues)}")
            return False
        else:
            print("✅ All fields are properly set")
    else:
        print("❌ Booking was not created")
        return False
    
    conn.close()
    return True

def test_database_cleanup():
    """Test that legacy database issues have been cleaned up"""
    print("\n=== TESTING DATABASE CLEANUP ===")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Test 1: Check for bookings with "Subscription" values
    print("\nTest 1: Checking for 'Subscription' service labels")
    subscription_bookings = cur.execute("""
        SELECT COUNT(*) FROM bookings 
        WHERE service = 'Subscription' OR service_type = 'Subscription' OR service_name = 'Subscription'
    """).fetchone()[0]
    
    if subscription_bookings == 0:
        print("✅ No bookings with 'Subscription' labels found")
    else:
        print(f"❌ Found {subscription_bookings} bookings with 'Subscription' labels")
        return False
    
    # Test 2: Check for bookings with missing client_id
    print("\nTest 2: Checking for missing client_id values")
    missing_client_bookings = cur.execute("""
        SELECT COUNT(*) FROM bookings 
        WHERE client_id IS NULL OR client_id = 0
    """).fetchone()[0]
    
    if missing_client_bookings == 0:
        print("✅ No bookings with missing client_id found")
    else:
        print(f"❌ Found {missing_client_bookings} bookings with missing client_id")
        return False
    
    # Test 3: Check for bookings with generic service labels
    print("\nTest 3: Checking for generic service labels")
    generic_bookings = cur.execute("""
        SELECT COUNT(*) FROM bookings 
        WHERE service IS NULL OR service = '' OR service = 'Service' OR service = 'None'
           OR service_type IS NULL OR service_type = '' OR service_type = 'SERVICE'
    """).fetchone()[0]
    
    if generic_bookings == 0:
        print("✅ No bookings with generic service labels found")
    else:
        print(f"❌ Found {generic_bookings} bookings with generic service labels")
        # Show some examples
        examples = cur.execute("""
            SELECT id, client_id, service, service_type, service_name
            FROM bookings 
            WHERE service IS NULL OR service = '' OR service = 'Service' OR service = 'None'
               OR service_type IS NULL OR service_type = '' OR service_type = 'SERVICE'
            LIMIT 5
        """).fetchall()
        for ex in examples:
            print(f"   ID {ex['id']}: service='{ex['service']}', service_type='{ex['service_type']}'")
        return False
    
    conn.close()
    return True

def test_service_type_derivation():
    """Test the service type derivation logic"""
    print("\n=== TESTING SERVICE TYPE DERIVATION ===")
    
    # Import the function from stripe_invoice_bookings
    from stripe_invoice_bookings import service_type_from_label
    
    test_cases = [
        ("Daycare (Single Day)", "DAYCARE_SINGLE"),
        ("Short Walk", "WALK_SHORT"),
        ("Long Walk", "WALK_LONG"),
        ("Home Visit – 30m (1×/day)", "HOME_VISIT_30M_SINGLE"),
        ("Poop Scoop – One-time", "SCOOP_SINGLE"),
        ("Dog Walking Service", "DOG_WALKING_SERVICE"),
        ("", "SERVICE"),
        (None, "SERVICE"),
    ]
    
    all_passed = True
    for label, expected in test_cases:
        result = service_type_from_label(label)
        if result == expected:
            print(f"✅ '{label}' -> '{result}'")
        else:
            print(f"❌ '{label}' -> '{result}' (expected '{expected}')")
            all_passed = False
    
    return all_passed

def test_booking_validation():
    """Test that bookings have all required fields properly set"""
    print("\n=== TESTING BOOKING VALIDATION ===")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get all bookings and validate them
    bookings = cur.execute("""
        SELECT id, client_id, service, service_type, service_name, start_dt, end_dt, location, dogs
        FROM bookings 
        WHERE COALESCE(deleted, 0) = 0
        ORDER BY id DESC
        LIMIT 20
    """).fetchall()
    
    if not bookings:
        print("No bookings found to validate")
        return True
    
    print(f"Validating {len(bookings)} recent bookings...")
    
    issues_found = 0
    for booking in bookings:
        booking_issues = []
        
        # Check client_id
        if not booking['client_id']:
            booking_issues.append("Missing client_id")
        
        # Check service fields
        if not booking['service'] or booking['service'].strip().lower() in ['subscription', 'service', 'none', '']:
            booking_issues.append(f"Invalid service: '{booking['service']}'")
        
        if not booking['service_type'] or booking['service_type'].strip().lower() in ['subscription', 'service', 'none', '']:
            booking_issues.append(f"Invalid service_type: '{booking['service_type']}'")
        
        # Check required datetime fields
        if not booking['start_dt']:
            booking_issues.append("Missing start_dt")
        if not booking['end_dt']:
            booking_issues.append("Missing end_dt")
        
        # Check dogs count
        if not booking['dogs'] or booking['dogs'] < 1:
            booking_issues.append(f"Invalid dogs count: {booking['dogs']}")
        
        if booking_issues:
            print(f"❌ Booking {booking['id']}: {', '.join(booking_issues)}")
            issues_found += 1
        else:
            print(f"✅ Booking {booking['id']}: All fields valid")
    
    if issues_found == 0:
        print(f"✅ All {len(bookings)} bookings passed validation")
        return True
    else:
        print(f"❌ Found issues in {issues_found} out of {len(bookings)} bookings")
        return False

def main():
    """Run all tests"""
    print("BOOKING FIXES TEST SUITE")
    print("========================")
    print(f"Started at: {datetime.now()}")
    
    tests = [
        ("Booking Creation", test_booking_creation),
        ("Database Cleanup", test_database_cleanup),
        ("Service Type Derivation", test_service_type_derivation),
        ("Booking Validation", test_booking_validation),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)
        
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*50}")
    print("TEST RESULTS SUMMARY")
    print('='*50)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        if result:
            print(f"✅ {test_name}: PASSED")
            passed += 1
        else:
            print(f"❌ {test_name}: FAILED")
            failed += 1
    
    print(f"\nTotal: {passed + failed} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! Booking fixes are working correctly.")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the issues above.")
    
    print(f"\nCompleted at: {datetime.now()}")
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
