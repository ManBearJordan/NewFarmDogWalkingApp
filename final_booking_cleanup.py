#!/usr/bin/env python3
"""
Final comprehensive cleanup of all booking issues.
This script fixes all remaining booking data issues.
"""

import sqlite3
import sys
import os
from datetime import datetime

# Add the current directory to Python path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import get_conn, backup_db

def fix_all_subscription_issues():
    """Fix all variations of subscription-related issues"""
    conn = get_conn()
    cur = conn.cursor()
    
    print("=== FIXING ALL SUBSCRIPTION ISSUES ===")
    
    # Find all bookings with any variation of "subscription" in service fields
    cur.execute("""
        SELECT id, client_id, service, service_type, service_name
        FROM bookings 
        WHERE LOWER(service) LIKE '%subscription%' 
           OR LOWER(service_type) LIKE '%subscription%' 
           OR LOWER(service_name) LIKE '%subscription%'
           OR service_type = 'SUBSCRIPTION'
           OR service = 'SUBSCRIPTION'
           OR service_name = 'SUBSCRIPTION'
        ORDER BY id DESC
    """)
    
    subscription_bookings = cur.fetchall()
    fixed_count = 0
    
    if not subscription_bookings:
        print("No subscription-related bookings found to fix")
        return 0
    
    print(f"Found {len(subscription_bookings)} bookings with subscription-related issues")
    
    for booking in subscription_bookings:
        booking_id = booking['id']
        
        # Set proper service values
        service_label = "Dog Walking Service"
        service_type = "WALK_GENERAL"
        
        # Update the booking
        cur.execute("""
            UPDATE bookings 
            SET service = ?, service_type = ?, service_name = ?
            WHERE id = ?
        """, (service_label, service_type, service_label, booking_id))
        
        print(f"  Fixed booking {booking_id}: '{service_label}' ({service_type})")
        fixed_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"Fixed {fixed_count} subscription-related bookings")
    return fixed_count

def fix_service_name_issues():
    """Fix service_name field issues"""
    conn = get_conn()
    cur = conn.cursor()
    
    print("\n=== FIXING SERVICE_NAME ISSUES ===")
    
    # Find bookings with None or empty service_name
    cur.execute("""
        SELECT id, service, service_type, service_name
        FROM bookings 
        WHERE service_name IS NULL 
           OR service_name = 'None' 
           OR service_name = ''
        ORDER BY id DESC
    """)
    
    name_issues = cur.fetchall()
    fixed_count = 0
    
    if not name_issues:
        print("No service_name issues found")
        return 0
    
    print(f"Found {len(name_issues)} bookings with service_name issues")
    
    for booking in name_issues:
        booking_id = booking['id']
        service = booking['service'] or "Dog Walking Service"
        
        # Use service field as service_name, or default
        service_name = service if service and service != 'None' else "Dog Walking Service"
        
        cur.execute("""
            UPDATE bookings 
            SET service_name = ?
            WHERE id = ?
        """, (service_name, booking_id))
        
        print(f"  Fixed booking {booking_id}: service_name = '{service_name}'")
        fixed_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"Fixed {fixed_count} service_name issues")
    return fixed_count

def validate_all_bookings():
    """Validate all bookings have proper values"""
    conn = get_conn()
    cur = conn.cursor()
    
    print("\n=== VALIDATING ALL BOOKINGS ===")
    
    # Get all bookings
    cur.execute("""
        SELECT id, client_id, service, service_type, service_name, start_dt, end_dt, dogs
        FROM bookings 
        WHERE COALESCE(deleted, 0) = 0
        ORDER BY id DESC
    """)
    
    bookings = cur.fetchall()
    issues_found = 0
    
    print(f"Validating {len(bookings)} bookings...")
    
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
        
        if not booking['service_name'] or booking['service_name'].strip().lower() in ['subscription', 'service', 'none', '']:
            booking_issues.append(f"Invalid service_name: '{booking['service_name']}'")
        
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
    
    if issues_found == 0:
        print(f"✅ All {len(bookings)} bookings passed validation")
    else:
        print(f"❌ Found issues in {issues_found} out of {len(bookings)} bookings")
    
    conn.close()
    return issues_found == 0

def main():
    """Main cleanup function"""
    print("FINAL BOOKING CLEANUP")
    print("====================")
    print(f"Started at: {datetime.now()}")
    
    # Create backup before making changes
    print("\nCreating database backup...")
    backup_db()
    print("Backup created successfully")
    
    # Apply all fixes
    total_fixed = 0
    total_fixed += fix_all_subscription_issues()
    total_fixed += fix_service_name_issues()
    
    print(f"\n=== FINAL RESULTS ===")
    print(f"Total bookings fixed: {total_fixed}")
    
    # Final validation
    print("\nRunning final validation...")
    validation_passed = validate_all_bookings()
    
    if validation_passed:
        print("\n✅ ALL BOOKING ISSUES HAVE BEEN RESOLVED!")
        print("All bookings now have proper client_id, service_type, and service labels.")
    else:
        print("\n⚠️  Some issues remain - manual review may be needed")
    
    print(f"\nCompleted at: {datetime.now()}")
    return validation_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
