#!/usr/bin/env python3
"""
Execute the simple duplicate cleanup SQL query.

This script removes duplicate bookings using the provided SQL:
DELETE FROM bookings
WHERE id NOT IN (
  SELECT MIN(id) FROM bookings
  GROUP BY client_id, service_type, start, end
);

This keeps the booking with the lowest ID for each unique combination.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

def backup_database():
    """Create a backup before making changes"""
    if not os.path.exists(DB_PATH):
        print("❌ Database not found!")
        return False
    
    backup_dir = os.path.join(os.path.dirname(__file__), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(backup_dir, f"pre-simple-cleanup-{timestamp}.db")
    
    with open(DB_PATH, 'rb') as src, open(backup_path, 'wb') as dst:
        dst.write(src.read())
    
    print(f"✅ Database backed up to: {backup_path}")
    return True

def check_duplicates_before():
    """Check for duplicates before cleanup"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    print("🔍 Checking for duplicates before cleanup...")
    
    # Count total bookings
    cur.execute("SELECT COUNT(*) FROM bookings WHERE COALESCE(deleted, 0) = 0")
    total_bookings = cur.fetchone()[0]
    
    # Find duplicate groups
    cur.execute("""
        SELECT client_id, service_type, start, end, COUNT(*) as count,
               GROUP_CONCAT(id) as ids,
               GROUP_CONCAT(stripe_invoice_id) as invoice_ids
        FROM bookings
        WHERE COALESCE(deleted, 0) = 0
        GROUP BY client_id, service_type, start, end
        HAVING COUNT(*) > 1
        ORDER BY count DESC
    """)
    
    duplicates = cur.fetchall()
    
    print(f"📊 Total active bookings: {total_bookings}")
    print(f"📊 Duplicate groups found: {len(duplicates)}")
    
    if duplicates:
        total_duplicates = sum(row['count'] - 1 for row in duplicates)  # -1 because we keep one
        print(f"📊 Total duplicate bookings to be removed: {total_duplicates}")
        
        print("\n🔍 Sample duplicate groups:")
        for i, row in enumerate(duplicates[:5]):  # Show first 5 groups
            ids = row['ids'].split(',')
            invoices = row['invoice_ids'].split(',') if row['invoice_ids'] else ['None'] * len(ids)
            print(f"  Group {i+1}: Client {row['client_id']}, {row['service_type']}")
            print(f"    Time: {row['start']} to {row['end']}")
            print(f"    IDs: {ids} (will keep ID {min(int(x) for x in ids)})")
            print(f"    Invoices: {invoices}")
            print()
    else:
        print("✅ No duplicates found!")
    
    conn.close()
    return len(duplicates) > 0

def execute_cleanup():
    """Execute the duplicate cleanup SQL"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    print("🧹 Executing duplicate cleanup...")
    
    # Execute the provided SQL query
    cur.execute("""
        DELETE FROM bookings
        WHERE id NOT IN (
          SELECT MIN(id) FROM bookings
          GROUP BY client_id, service_type, start, end
        )
    """)
    
    deleted_count = cur.rowcount
    print(f"✅ Deleted {deleted_count} duplicate bookings")
    
    conn.commit()
    conn.close()
    
    return deleted_count

def verify_cleanup():
    """Verify that no duplicates remain"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    print("🔍 Verifying cleanup results...")
    
    # Check for remaining duplicates
    cur.execute("""
        SELECT client_id, service_type, start, end, COUNT(*) as count
        FROM bookings
        WHERE COALESCE(deleted, 0) = 0
        GROUP BY client_id, service_type, start, end
        HAVING COUNT(*) > 1
    """)
    
    remaining_duplicates = cur.fetchall()
    
    if remaining_duplicates:
        print(f"⚠️  WARNING: {len(remaining_duplicates)} duplicate groups still remain!")
        for row in remaining_duplicates:
            print(f"  Client {row['client_id']}, {row['service_type']}, {row['start']} ({row['count']} copies)")
    else:
        print("✅ No duplicate bookings remain - cleanup successful!")
    
    # Show final statistics
    cur.execute("SELECT COUNT(*) FROM bookings WHERE COALESCE(deleted, 0) = 0")
    total_bookings = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM bookings WHERE stripe_invoice_id IS NOT NULL AND COALESCE(deleted, 0) = 0")
    invoiced_bookings = cur.fetchone()[0]
    
    print(f"\n📊 Final Statistics:")
    print(f"  Total active bookings: {total_bookings}")
    print(f"  Invoiced bookings: {invoiced_bookings}")
    print(f"  Non-invoiced bookings: {total_bookings - invoiced_bookings}")
    
    conn.close()
    
    return len(remaining_duplicates) == 0

def main():
    print("🧹 Simple Duplicate Booking Cleanup")
    print("=" * 50)
    print("This will execute the SQL query:")
    print("DELETE FROM bookings")
    print("WHERE id NOT IN (")
    print("  SELECT MIN(id) FROM bookings")
    print("  GROUP BY client_id, service_type, start, end")
    print(");")
    print()
    
    # Check if there are duplicates to clean up
    has_duplicates = check_duplicates_before()
    
    if not has_duplicates:
        print("✅ No cleanup needed - no duplicates found!")
        return
    
    print()
    response = input("This will modify your database. Continue? (y/N): ")
    if response.lower() != 'y':
        print("Cleanup cancelled.")
        return
    
    # Create backup
    if not backup_database():
        print("❌ Failed to create backup. Aborting.")
        return
    
    # Execute cleanup
    deleted_count = execute_cleanup()
    
    # Verify results
    success = verify_cleanup()
    
    print(f"\n🎉 Cleanup completed!")
    print(f"   Removed {deleted_count} duplicate bookings")
    
    if success:
        print("✅ All duplicates successfully removed")
    else:
        print("⚠️  Some duplicates may still remain - check the output above")

if __name__ == "__main__":
    main()
