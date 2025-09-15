#!/usr/bin/env python3
"""
Script to verify the cleanup operation and check data integrity
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

def verify_cleanup():
    """Verify the cleanup operation and check data integrity"""
    
    if not os.path.exists(DB_PATH):
        print(f"Database file not found: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    try:
        print("=== CLEANUP VERIFICATION REPORT ===")
        print()
        
        # Check total bookings
        cur.execute("SELECT COUNT(*) as count FROM bookings")
        total_bookings = cur.fetchone()[0]
        print(f"Total bookings in database: {total_bookings}")
        
        # Check for NULL service_type
        cur.execute("SELECT COUNT(*) as count FROM bookings WHERE service_type IS NULL")
        null_service_type = cur.fetchone()[0]
        print(f"Bookings with NULL service_type: {null_service_type}")
        
        # Check for empty string service_type
        cur.execute("SELECT COUNT(*) as count FROM bookings WHERE service_type = ''")
        empty_service_type = cur.fetchone()[0]
        print(f"Bookings with empty service_type: {empty_service_type}")
        
        # Show distribution of service_type values
        cur.execute("""
            SELECT service_type, COUNT(*) as count 
            FROM bookings 
            GROUP BY service_type 
            ORDER BY count DESC
        """)
        service_types = cur.fetchall()
        print(f"\nService type distribution:")
        for row in service_types:
            service_type = row[0] if row[0] is not None else "NULL"
            count = row[1]
            print(f"  {service_type}: {count}")
        
        # Check for any potential data integrity issues
        print(f"\n=== DATA INTEGRITY CHECKS ===")
        
        # Check for bookings without clients
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM bookings b 
            LEFT JOIN clients c ON b.client_id = c.id 
            WHERE c.id IS NULL
        """)
        orphaned_bookings = cur.fetchone()[0]
        print(f"Bookings without valid clients: {orphaned_bookings}")
        
        # Check for bookings with invalid dates
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM bookings 
            WHERE start_dt IS NULL OR end_dt IS NULL OR start_dt = '' OR end_dt = ''
        """)
        invalid_dates = cur.fetchone()[0]
        print(f"Bookings with invalid dates: {invalid_dates}")
        
        # Summary
        print(f"\n=== SUMMARY ===")
        if null_service_type == 0:
            print("✓ SUCCESS: No bookings with NULL service_type found")
        else:
            print(f"⚠ WARNING: {null_service_type} bookings still have NULL service_type")
            
        if orphaned_bookings == 0 and invalid_dates == 0:
            print("✓ Data integrity checks passed")
        else:
            print("⚠ Some data integrity issues found (see above)")
            
    except Exception as e:
        print(f"Error during verification: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    verify_cleanup()
