#!/usr/bin/env python3
"""
Final cleanup of orphaned and test data to ensure clean UI display.
"""

import sqlite3
import sys
import os
from datetime import datetime

# Add the current directory to Python path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import get_conn, backup_db

def cleanup_orphaned_data():
    """Remove orphaned bookings and test data"""
    conn = get_conn()
    cur = conn.cursor()
    
    print("=== CLEANING UP ORPHANED DATA ===")
    
    # Remove bookings with NULL client_id
    cur.execute("DELETE FROM bookings WHERE client_id IS NULL")
    deleted_null_client = cur.rowcount
    print(f"Deleted {deleted_null_client} bookings with NULL client_id")
    
    # Remove bookings with NULL service_type
    cur.execute("DELETE FROM bookings WHERE service_type IS NULL OR service_type = ''")
    deleted_null_service = cur.rowcount
    print(f"Deleted {deleted_null_service} bookings with NULL/empty service_type")
    
    # Remove any remaining "Subscription Customer" clients that are placeholders
    cur.execute("""
        DELETE FROM clients 
        WHERE name = 'Subscription Customer' 
        AND email LIKE 'sub_%@placeholder.com'
    """)
    deleted_placeholder_clients = cur.rowcount
    print(f"Deleted {deleted_placeholder_clients} placeholder subscription clients")
    
    # Remove orphaned bookings (client_id points to non-existent client)
    cur.execute("""
        DELETE FROM bookings 
        WHERE client_id NOT IN (SELECT id FROM clients)
    """)
    deleted_orphaned = cur.rowcount
    print(f"Deleted {deleted_orphaned} orphaned bookings")
    
    conn.commit()
    conn.close()
    
    total_cleaned = deleted_null_client + deleted_null_service + deleted_placeholder_clients + deleted_orphaned
    print(f"\nTotal records cleaned: {total_cleaned}")
    return total_cleaned

def main():
    """Main cleanup function"""
    print("FINAL ORPHANED DATA CLEANUP")
    print("===========================")
    print(f"Started at: {datetime.now()}")
    
    # Create backup before making changes
    print("\nCreating database backup...")
    backup_db()
    print("Backup created successfully")
    
    # Clean up orphaned data
    total_cleaned = cleanup_orphaned_data()
    
    print(f"\n=== CLEANUP COMPLETE ===")
    if total_cleaned > 0:
        print(f"✅ Cleaned up {total_cleaned} orphaned records")
        print("The UI should now show only valid bookings with proper client and service information.")
    else:
        print("✅ No orphaned data found - database is clean!")
    
    print(f"\nCompleted at: {datetime.now()}")

if __name__ == "__main__":
    main()
