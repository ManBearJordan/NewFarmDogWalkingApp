#!/usr/bin/env python3
"""
One-time cleanup script for duplicate bookings.

This script removes duplicate bookings that may have been created before
the unique constraint was implemented. It follows the strategy:

1. Remove non-invoiced duplicates when an invoiced copy exists for same slot
2. Collapse any remaining exact duplicates (keep one with lowest ID)

Run this once after implementing the unique constraint to clean up existing data.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

def backup_database():
    """Create a backup before making changes"""
    if not os.path.exists(DB_PATH):
        print("Database not found!")
        return False
    
    backup_dir = os.path.join(os.path.dirname(__file__), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(backup_dir, f"pre-cleanup-duplicates-{timestamp}.db")
    
    with open(DB_PATH, 'rb') as src, open(backup_path, 'wb') as dst:
        dst.write(src.read())
    
    print(f"✅ Database backed up to: {backup_path}")
    return True

def cleanup_duplicate_bookings():
    """Clean up duplicate bookings following the specified strategy"""
    
    if not backup_database():
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    print("🧹 Starting duplicate booking cleanup...")
    
    # Step 1: Remove non-invoiced duplicates when an invoiced copy exists for same slot
    print("\n📋 Step 1: Removing non-invoiced duplicates when invoiced copy exists...")
    
    cur.execute("""
        SELECT COUNT(*) FROM bookings b
        WHERE b.stripe_invoice_id IS NULL
          AND EXISTS (
            SELECT 1
            FROM bookings x
            WHERE x.client_id = b.client_id
              AND x.service_type = b.service_type
              AND x.start = b.start
              AND x.end = b.end
              AND x.stripe_invoice_id IS NOT NULL
              AND COALESCE(x.deleted, 0) = 0
          )
          AND COALESCE(b.deleted, 0) = 0
    """)
    
    non_invoiced_dupes = cur.fetchone()[0]
    print(f"Found {non_invoiced_dupes} non-invoiced duplicates with invoiced copies")
    
    if non_invoiced_dupes > 0:
        # Show some examples before deletion
        cur.execute("""
            SELECT b.id, b.client_id, b.service_type, b.start, b.end, 
                   'NO INVOICE' as invoice_status
            FROM bookings b
            WHERE b.stripe_invoice_id IS NULL
              AND EXISTS (
                SELECT 1
                FROM bookings x
                WHERE x.client_id = b.client_id
                  AND x.service_type = b.service_type
                  AND x.start = b.start
                  AND x.end = b.end
                  AND x.stripe_invoice_id IS NOT NULL
                  AND COALESCE(x.deleted, 0) = 0
              )
              AND COALESCE(b.deleted, 0) = 0
            LIMIT 5
        """)
        
        examples = cur.fetchall()
        print("\nExamples of bookings to be removed:")
        for row in examples:
            print(f"  ID {row['id']}: Client {row['client_id']}, {row['service_type']}, {row['start']}")
        
        # Delete non-invoiced duplicates
        cur.execute("""
            DELETE FROM bookings 
            WHERE id IN (
                SELECT b.id FROM bookings b
                WHERE b.stripe_invoice_id IS NULL
                  AND EXISTS (
                    SELECT 1
                    FROM bookings x
                    WHERE x.client_id = b.client_id
                      AND x.service_type = b.service_type
                      AND x.start = b.start
                      AND x.end = b.end
                      AND x.stripe_invoice_id IS NOT NULL
                      AND COALESCE(x.deleted, 0) = 0
                  )
                  AND COALESCE(b.deleted, 0) = 0
            )
        """)
        
        deleted_count = cur.rowcount
        print(f"✅ Deleted {deleted_count} non-invoiced duplicate bookings")
    
    # Step 2: Collapse any remaining exact duplicates (keep one with lowest ID)
    print("\n📋 Step 2: Collapsing remaining exact duplicates...")
    
    # Find groups of exact duplicates
    cur.execute("""
        SELECT client_id, service_type, start, end, COUNT(*) as count,
               GROUP_CONCAT(id) as ids
        FROM bookings
        WHERE COALESCE(deleted, 0) = 0
        GROUP BY client_id, service_type, start, end
        HAVING COUNT(*) > 1
    """)
    
    duplicate_groups = cur.fetchall()
    print(f"Found {len(duplicate_groups)} groups of exact duplicates")
    
    total_to_delete = 0
    for group in duplicate_groups:
        ids = [int(x) for x in group['ids'].split(',')]
        # Keep the one with the lowest ID (first created)
        keep_id = min(ids)
        delete_ids = [x for x in ids if x != keep_id]
        total_to_delete += len(delete_ids)
        
        print(f"  Group: Client {group['client_id']}, {group['service_type']}, {group['start']}")
        print(f"    Keeping ID {keep_id}, deleting IDs {delete_ids}")
    
    if total_to_delete > 0:
        # Delete the duplicates (keep the one with minimum rowid/id)
        cur.execute("""
            DELETE FROM bookings
            WHERE rowid NOT IN (
                SELECT MIN(rowid)
                FROM bookings
                WHERE COALESCE(deleted, 0) = 0
                GROUP BY client_id, service_type, start, end
            )
            AND COALESCE(deleted, 0) = 0
        """)
        
        deleted_count = cur.rowcount
        print(f"✅ Deleted {deleted_count} remaining duplicate bookings")
    
    # Step 3: Verify the unique constraint can be applied
    print("\n📋 Step 3: Verifying cleanup results...")
    
    cur.execute("""
        SELECT client_id, service_type, start, end, COUNT(*) as count
        FROM bookings
        WHERE COALESCE(deleted, 0) = 0
        GROUP BY client_id, service_type, start, end
        HAVING COUNT(*) > 1
    """)
    
    remaining_dupes = cur.fetchall()
    
    if remaining_dupes:
        print(f"⚠️  WARNING: {len(remaining_dupes)} duplicate groups still remain:")
        for dupe in remaining_dupes:
            print(f"  Client {dupe['client_id']}, {dupe['service_type']}, {dupe['start']} ({dupe['count']} copies)")
    else:
        print("✅ No duplicate bookings remain - unique constraint can be safely applied")
    
    # Step 4: Show summary statistics
    print("\n📊 Summary:")
    cur.execute("SELECT COUNT(*) FROM bookings WHERE COALESCE(deleted, 0) = 0")
    total_bookings = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM bookings WHERE stripe_invoice_id IS NOT NULL AND COALESCE(deleted, 0) = 0")
    invoiced_bookings = cur.fetchone()[0]
    
    print(f"  Total active bookings: {total_bookings}")
    print(f"  Invoiced bookings: {invoiced_bookings}")
    print(f"  Non-invoiced bookings: {total_bookings - invoiced_bookings}")
    
    conn.commit()
    conn.close()
    
    print("\n🎉 Cleanup completed successfully!")
    print("\nNext steps:")
    print("1. Test the application to ensure everything works correctly")
    print("2. The unique constraint is already in place via db.py")
    print("3. Future bookings will automatically use UPSERT to prevent duplicates")

if __name__ == "__main__":
    print("🧹 Duplicate Booking Cleanup Script")
    print("=" * 50)
    
    response = input("This will modify your database. Continue? (y/N): ")
    if response.lower() != 'y':
        print("Cleanup cancelled.")
        exit(0)
    
    cleanup_duplicate_bookings()
