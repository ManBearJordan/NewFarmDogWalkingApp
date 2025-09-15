#!/usr/bin/env python3
"""
Quick test to verify the current state of bookings and check for any duplicates.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

def test_current_state():
    """Test the current state of the bookings table"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    print("🔍 Current Database State Analysis")
    print("=" * 50)
    
    # Check total bookings
    cur.execute("SELECT COUNT(*) FROM bookings")
    total_all = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM bookings WHERE COALESCE(deleted, 0) = 0")
    total_active = cur.fetchone()[0]
    
    print(f"📊 Total bookings (all): {total_all}")
    print(f"📊 Total active bookings: {total_active}")
    
    # Check for duplicates using the same logic as your SQL
    cur.execute("""
        SELECT client_id, service_type, start, end, COUNT(*) as count,
               GROUP_CONCAT(id) as ids
        FROM bookings
        GROUP BY client_id, service_type, start, end
        HAVING COUNT(*) > 1
    """)
    
    duplicates_all = cur.fetchall()
    
    # Check for duplicates in active bookings only
    cur.execute("""
        SELECT client_id, service_type, start, end, COUNT(*) as count,
               GROUP_CONCAT(id) as ids
        FROM bookings
        WHERE COALESCE(deleted, 0) = 0
        GROUP BY client_id, service_type, start, end
        HAVING COUNT(*) > 1
    """)
    
    duplicates_active = cur.fetchall()
    
    print(f"📊 Duplicate groups (all bookings): {len(duplicates_all)}")
    print(f"📊 Duplicate groups (active only): {len(duplicates_active)}")
    
    # Show sample bookings
    print(f"\n📋 Sample bookings:")
    cur.execute("""
        SELECT id, client_id, service_type, start, end, 
               COALESCE(deleted, 0) as deleted,
               stripe_invoice_id
        FROM bookings 
        ORDER BY id 
        LIMIT 10
    """)
    
    bookings = cur.fetchall()
    for booking in bookings:
        status = "DELETED" if booking['deleted'] else "ACTIVE"
        invoice = booking['stripe_invoice_id'] or "No Invoice"
        print(f"  ID {booking['id']}: Client {booking['client_id']}, {booking['service_type']}")
        print(f"    Time: {booking['start']} to {booking['end']}")
        print(f"    Status: {status}, Invoice: {invoice}")
        print()
    
    # Test the exact SQL query that would be executed
    print("🧪 Testing the SQL query logic...")
    cur.execute("""
        SELECT id FROM bookings
        WHERE id NOT IN (
          SELECT MIN(id) FROM bookings
          GROUP BY client_id, service_type, start, end
        )
    """)
    
    would_be_deleted = cur.fetchall()
    print(f"📊 Bookings that would be deleted by your SQL: {len(would_be_deleted)}")
    
    if would_be_deleted:
        print("   IDs that would be deleted:", [row['id'] for row in would_be_deleted])
    
    conn.close()
    
    return len(duplicates_active) == 0

if __name__ == "__main__":
    success = test_current_state()
    if success:
        print("✅ Database is clean - no duplicates found!")
    else:
        print("⚠️  Duplicates detected!")
