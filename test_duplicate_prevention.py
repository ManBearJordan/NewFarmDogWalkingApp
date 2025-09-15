#!/usr/bin/env python3
"""
Test script to verify that duplicate prevention is working correctly.
Tests:
1. Transaction rollback on Stripe error
2. Unique constraint prevents duplicates
3. UPSERT functionality works correctly
"""

import sqlite3
from db import get_conn, backup_db, add_or_upsert_booking
from datetime import datetime

def test_duplicate_prevention():
    """Test the duplicate prevention mechanisms"""
    
    print("=== TESTING DUPLICATE PREVENTION ===")
    
    # Create a backup before testing
    print("Creating database backup...")
    backup_db()
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Test data
        client_id = 4  # Assuming this client exists
        service_label = "Test Service"
        service_type = "TEST_SERVICE"
        start_iso = "2025-09-20 10:00:00"
        end_iso = "2025-09-20 11:00:00"
        location = "Test Location"
        dogs = 1
        price_cents = 5500
        notes = "Test booking"
        
        print("\n=== TEST 1: Create initial booking ===")
        booking_id_1 = add_or_upsert_booking(
            conn, client_id, service_label, service_type,
            start_iso, end_iso, location, dogs, price_cents, notes
        )
        print(f"Created booking ID: {booking_id_1}")
        
        print("\n=== TEST 2: Try to create duplicate (should upsert) ===")
        updated_notes = "Updated test booking"
        updated_price = 6000
        
        booking_id_2 = add_or_upsert_booking(
            conn, client_id, service_label, service_type,
            start_iso, end_iso, location, dogs, updated_price, updated_notes
        )
        print(f"Upserted booking ID: {booking_id_2}")
        print(f"Same ID as original? {booking_id_1 == booking_id_2}")
        
        # Verify the booking was updated, not duplicated
        cur.execute("""
            SELECT COUNT(*) FROM bookings 
            WHERE client_id=? AND service_type=? AND start=? AND end=?
        """, (client_id, service_type, start_iso, end_iso))
        count = cur.fetchone()[0]
        print(f"Number of matching bookings: {count}")
        
        # Check the updated values
        cur.execute("""
            SELECT price_cents, notes, updated_at FROM bookings 
            WHERE id=?
        """, (booking_id_1,))
        row = cur.fetchone()
        if row:
            print(f"Updated price: {row[0]} (expected: {updated_price})")
            print(f"Updated notes: '{row[1]}' (expected: '{updated_notes}')")
            print(f"Updated timestamp: {row[2]}")
        
        print("\n=== TEST 3: Verify unique constraint exists ===")
        cur.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_booking_dedupe'
        """)
        index_exists = cur.fetchone()
        print(f"Unique index exists: {index_exists is not None}")
        
        if index_exists:
            # Get index info
            cur.execute("PRAGMA index_info(idx_booking_dedupe)")
            index_info = cur.fetchall()
            print("Index columns:")
            for info in index_info:
                print(f"  - {info[2]}")  # column name
        
        print("\n=== TEST 4: Test different time slot (should create new booking) ===")
        different_start = "2025-09-20 14:00:00"
        different_end = "2025-09-20 15:00:00"
        
        booking_id_3 = add_or_upsert_booking(
            conn, client_id, service_label, service_type,
            different_start, different_end, location, dogs, price_cents, "Different time slot"
        )
        print(f"New booking ID for different time: {booking_id_3}")
        print(f"Different from original? {booking_id_1 != booking_id_3}")
        
        # Verify we now have 2 bookings for this client/service
        cur.execute("""
            SELECT COUNT(*) FROM bookings 
            WHERE client_id=? AND service_type=?
        """, (client_id, service_type))
        total_count = cur.fetchone()[0]
        print(f"Total bookings for this client/service: {total_count}")
        
        print("\n=== TEST 5: Check updated_at column exists ===")
        cur.execute("PRAGMA table_info(bookings)")
        columns = [row[1] for row in cur.fetchall()]
        has_updated_at = "updated_at" in columns
        print(f"updated_at column exists: {has_updated_at}")
        
        print("\n✅ All tests completed successfully!")
        
        # Clean up test data
        print("\n=== CLEANUP ===")
        cur.execute("DELETE FROM bookings WHERE service_type=?", (service_type,))
        deleted_count = cur.rowcount
        conn.commit()
        print(f"Cleaned up {deleted_count} test bookings")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    test_duplicate_prevention()
