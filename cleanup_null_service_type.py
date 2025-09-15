#!/usr/bin/env python3
"""
Script to delete bookings where service_type IS NULL
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

def cleanup_null_service_type():
    """Execute DELETE FROM bookings WHERE service_type IS NULL"""
    
    if not os.path.exists(DB_PATH):
        print(f"Database file not found: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    try:
        # First, check how many records have NULL service_type
        cur.execute("SELECT COUNT(*) as count FROM bookings WHERE service_type IS NULL")
        null_count = cur.fetchone()[0]
        print(f"Found {null_count} bookings with NULL service_type")
        
        # Check total bookings before deletion
        cur.execute("SELECT COUNT(*) as count FROM bookings")
        total_before = cur.fetchone()[0]
        print(f"Total bookings before deletion: {total_before}")
        
        if null_count > 0:
            # Create backup before deletion
            backup_path = f"backups/pre-cleanup-null-service-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
            os.makedirs("backups", exist_ok=True)
            
            # Simple file copy for backup
            with open(DB_PATH, 'rb') as src, open(backup_path, 'wb') as dst:
                dst.write(src.read())
            print(f"Backup created: {backup_path}")
            
            # Execute the DELETE statement
            cur.execute("DELETE FROM bookings WHERE service_type IS NULL")
            deleted_count = cur.rowcount
            conn.commit()
            
            print(f"Successfully deleted {deleted_count} bookings with NULL service_type")
            
            # Verify deletion
            cur.execute("SELECT COUNT(*) as count FROM bookings")
            total_after = cur.fetchone()[0]
            print(f"Total bookings after deletion: {total_after}")
            
            # Double-check no NULL service_type records remain
            cur.execute("SELECT COUNT(*) as count FROM bookings WHERE service_type IS NULL")
            remaining_null = cur.fetchone()[0]
            print(f"Remaining bookings with NULL service_type: {remaining_null}")
            
        else:
            print("No bookings with NULL service_type found. No action needed.")
            
    except Exception as e:
        print(f"Error during cleanup: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    cleanup_null_service_type()
