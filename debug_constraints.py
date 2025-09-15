#!/usr/bin/env python3
"""
Debug script to check database constraints and indexes
"""

from db import get_conn

def debug_constraints():
    conn = get_conn()
    cur = conn.cursor()
    
    print("=== CHECKING DATABASE CONSTRAINTS ===")
    
    # Check all indexes
    print("\n1. All indexes:")
    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='index'")
    indexes = cur.fetchall()
    for idx in indexes:
        print(f"  - {idx[0]}: {idx[1]}")
    
    # Check dedupe indexes specifically
    print("\n2. Dedupe indexes:")
    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND name LIKE '%dedupe%'")
    dedupe_indexes = cur.fetchall()
    for idx in dedupe_indexes:
        print(f"  - {idx[0]}: {idx[1]}")
    
    if not dedupe_indexes:
        print("  No dedupe indexes found!")
    
    # Check bookings table structure
    print("\n3. Bookings table columns:")
    cur.execute("PRAGMA table_info(bookings)")
    columns = cur.fetchall()
    relevant_cols = []
    for col in columns:
        col_name = col[1]
        if col_name in ['client_id', 'service_type', 'start', 'end', 'updated_at']:
            relevant_cols.append(col_name)
            print(f"  - {col_name}: {col[2]} (nullable: {not col[3]})")
    
    print(f"\n4. Required columns present: {set(['client_id', 'service_type', 'start', 'end']) <= set(relevant_cols)}")
    
    # Try to create the index manually
    print("\n5. Attempting to create unique index manually...")
    try:
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_booking_dedupe_manual
            ON bookings(client_id, service_type, start, end)
        """)
        conn.commit()
        print("  ✓ Index created successfully")
        
        # Verify it was created
        cur.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND name='idx_booking_dedupe_manual'")
        result = cur.fetchone()
        if result:
            print(f"  ✓ Index verified: {result[1]}")
        else:
            print("  ❌ Index not found after creation")
            
    except Exception as e:
        print(f"  ❌ Failed to create index: {e}")
    
    conn.close()

if __name__ == "__main__":
    debug_constraints()
