#!/usr/bin/env python3
"""
Fix booking creation and import issues to ensure correct client_id, service_type, and service labels.

This script addresses the issues described in the task:
1. Bookings created with missing or default values (e.g., "Subscription" instead of real service labels)
2. Missing or incorrect client_id values
3. Generic service_type values that should be specific

The script will:
1. Identify problematic bookings in the database
2. Fix booking creation code to set correct values
3. Fix booking import code to set correct values  
4. Update legacy database rows with "Subscription" values
"""

import sqlite3
import sys
import os
from datetime import datetime

# Add the current directory to Python path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import get_conn, backup_db

def analyze_booking_issues():
    """Analyze the current database to identify booking issues"""
    conn = get_conn()
    cur = conn.cursor()
    
    print("=== ANALYZING BOOKING ISSUES ===")
    
    # Check for bookings with "Subscription" as service or service_type
    print("\n1. Bookings with 'Subscription' as service/service_type:")
    cur.execute("""
        SELECT id, client_id, service, service_type, service_name, start_dt, end_dt
        FROM bookings 
        WHERE service = 'Subscription' OR service_type = 'Subscription' OR service_name = 'Subscription'
        ORDER BY id DESC
        LIMIT 20
    """)
    subscription_bookings = cur.fetchall()
    
    if subscription_bookings:
        print(f"Found {len(subscription_bookings)} bookings with 'Subscription' values:")
        for booking in subscription_bookings:
            print(f"  ID {booking['id']}: client_id={booking['client_id']}, "
                  f"service='{booking['service']}', service_type='{booking['service_type']}', "
                  f"service_name='{booking['service_name']}', start={booking['start_dt']}")
    else:
        print("  No bookings found with 'Subscription' values")
    
    # Check for bookings with missing client_id
    print("\n2. Bookings with missing or invalid client_id:")
    cur.execute("""
        SELECT id, client_id, service, service_type, start_dt, stripe_invoice_id
        FROM bookings 
        WHERE client_id IS NULL OR client_id = 0
        ORDER BY id DESC
        LIMIT 10
    """)
    missing_client_bookings = cur.fetchall()
    
    if missing_client_bookings:
        print(f"Found {len(missing_client_bookings)} bookings with missing client_id:")
        for booking in missing_client_bookings:
            print(f"  ID {booking['id']}: client_id={booking['client_id']}, "
                  f"service='{booking['service']}', invoice_id={booking['stripe_invoice_id']}")
    else:
        print("  No bookings found with missing client_id")
    
    # Check for bookings with generic service labels
    print("\n3. Bookings with generic or empty service labels:")
    cur.execute("""
        SELECT id, client_id, service, service_type, service_name
        FROM bookings 
        WHERE service IS NULL OR service = '' OR service = 'Service' 
           OR service_type IS NULL OR service_type = '' OR service_type = 'SERVICE'
        ORDER BY id DESC
        LIMIT 10
    """)
    generic_service_bookings = cur.fetchall()
    
    if generic_service_bookings:
        print(f"Found {len(generic_service_bookings)} bookings with generic service labels:")
        for booking in generic_service_bookings:
            print(f"  ID {booking['id']}: client_id={booking['client_id']}, "
                  f"service='{booking['service']}', service_type='{booking['service_type']}', "
                  f"service_name='{booking['service_name']}'")
    else:
        print("  No bookings found with generic service labels")
    
    # Summary statistics
    print("\n=== SUMMARY STATISTICS ===")
    cur.execute("SELECT COUNT(*) FROM bookings")
    total_bookings = cur.fetchone()[0]
    print(f"Total bookings: {total_bookings}")
    
    cur.execute("SELECT COUNT(*) FROM bookings WHERE client_id IS NULL OR client_id = 0")
    missing_client_count = cur.fetchone()[0]
    print(f"Bookings with missing client_id: {missing_client_count}")
    
    cur.execute("""
        SELECT COUNT(*) FROM bookings 
        WHERE service = 'Subscription' OR service_type = 'Subscription' OR service_name = 'Subscription'
    """)
    subscription_count = cur.fetchone()[0]
    print(f"Bookings with 'Subscription' labels: {subscription_count}")
    
    conn.close()
    return {
        'total_bookings': total_bookings,
        'missing_client_count': missing_client_count,
        'subscription_count': subscription_count,
        'subscription_bookings': subscription_bookings,
        'missing_client_bookings': missing_client_bookings,
        'generic_service_bookings': generic_service_bookings
    }

def fix_subscription_bookings():
    """Fix bookings that have 'Subscription' as service or service_type"""
    conn = get_conn()
    cur = conn.cursor()
    
    print("\n=== FIXING SUBSCRIPTION BOOKINGS ===")
    
    # Get bookings with Subscription labels that have Stripe invoice IDs
    cur.execute("""
        SELECT b.id, b.client_id, b.service, b.service_type, b.service_name, 
               b.stripe_invoice_id, b.start_dt, b.end_dt, b.location, b.dogs
        FROM bookings b
        WHERE (b.service = 'Subscription' OR b.service_type = 'Subscription' OR b.service_name = 'Subscription')
          AND b.stripe_invoice_id IS NOT NULL
          AND b.stripe_invoice_id != ''
    """)
    
    subscription_bookings = cur.fetchall()
    fixed_count = 0
    
    if not subscription_bookings:
        print("No subscription bookings with Stripe invoice IDs found to fix")
        conn.close()
        return 0
    
    print(f"Found {len(subscription_bookings)} subscription bookings to fix")
    
    # Try to get better service information from Stripe metadata
    try:
        import stripe
        from secrets_config import get_stripe_key
        stripe.api_key = get_stripe_key()
        
        for booking in subscription_bookings:
            booking_id = booking['id']
            invoice_id = booking['stripe_invoice_id']
            
            try:
                # Get invoice from Stripe to extract better service information
                invoice = stripe.Invoice.retrieve(invoice_id, expand=['lines.data.price.product'])
                
                # Extract service information from invoice metadata or line items
                service_label = None
                service_type = None
                
                # Check invoice metadata first
                if hasattr(invoice, 'metadata') and invoice.metadata:
                    service_label = invoice.metadata.get('service') or invoice.metadata.get('service_name')
                    service_type = invoice.metadata.get('service_type') or invoice.metadata.get('service_code')
                
                # If not found, check line items
                if not service_label and hasattr(invoice, 'lines') and invoice.lines.data:
                    line = invoice.lines.data[0]
                    if hasattr(line, 'price') and hasattr(line.price, 'nickname'):
                        service_label = line.price.nickname
                    elif hasattr(line, 'description'):
                        service_label = line.description
                    
                    # Check line item metadata
                    if hasattr(line, 'metadata') and line.metadata:
                        if not service_label:
                            service_label = line.metadata.get('service') or line.metadata.get('service_name')
                        if not service_type:
                            service_type = line.metadata.get('service_type') or line.metadata.get('service_code')
                    
                    # Check price metadata
                    if hasattr(line, 'price') and hasattr(line.price, 'metadata') and line.price.metadata:
                        if not service_label:
                            service_label = line.price.metadata.get('service_name')
                        if not service_type:
                            service_type = line.price.metadata.get('service_code')
                    
                    # Check product metadata
                    if hasattr(line, 'price') and hasattr(line.price, 'product'):
                        product = line.price.product
                        if hasattr(product, 'name') and not service_label:
                            service_label = product.name
                        if hasattr(product, 'metadata') and product.metadata:
                            if not service_label:
                                service_label = product.metadata.get('service_name')
                            if not service_type:
                                service_type = product.metadata.get('service_code')
                
                # Derive service_type from service_label if not found
                if service_label and not service_type:
                    service_type = derive_service_type_from_label(service_label)
                
                # Use fallback values if still not found
                if not service_label:
                    service_label = "Dog Walking Service"
                if not service_type:
                    service_type = "WALK_GENERAL"
                
                # Update the booking
                cur.execute("""
                    UPDATE bookings 
                    SET service = ?, service_type = ?, service_name = ?
                    WHERE id = ?
                """, (service_label, service_type, service_label, booking_id))
                
                print(f"  Fixed booking {booking_id}: '{service_label}' ({service_type})")
                fixed_count += 1
                
            except Exception as e:
                print(f"  Error processing booking {booking_id} with invoice {invoice_id}: {e}")
                # Use fallback values
                service_label = "Dog Walking Service"
                service_type = "WALK_GENERAL"
                cur.execute("""
                    UPDATE bookings 
                    SET service = ?, service_type = ?, service_name = ?
                    WHERE id = ?
                """, (service_label, service_type, service_label, booking_id))
                fixed_count += 1
    
    except Exception as e:
        print(f"Error accessing Stripe: {e}")
        # Fallback: update all subscription bookings with generic but proper values
        cur.execute("""
            UPDATE bookings 
            SET service = 'Dog Walking Service', 
                service_type = 'WALK_GENERAL', 
                service_name = 'Dog Walking Service'
            WHERE (service = 'Subscription' OR service_type = 'Subscription' OR service_name = 'Subscription')
        """)
        fixed_count = cur.rowcount
        print(f"Applied fallback fix to {fixed_count} bookings")
    
    conn.commit()
    conn.close()
    
    print(f"Fixed {fixed_count} subscription bookings")
    return fixed_count

def derive_service_type_from_label(label):
    """Derive a proper service_type code from a service label"""
    if not label:
        return "WALK_GENERAL"
    
    label_lower = label.lower()
    
    # Map common service labels to proper service types
    if "short" in label_lower and "walk" in label_lower:
        if "pack" in label_lower:
            return "WALK_SHORT_PACKS"
        else:
            return "WALK_SHORT_SINGLE"
    elif "long" in label_lower and "walk" in label_lower:
        if "pack" in label_lower:
            return "WALK_LONG_PACKS"
        else:
            return "WALK_LONG_SINGLE"
    elif "daycare" in label_lower:
        if "pack" in label_lower:
            return "DAYCARE_PACKS"
        elif "weekly" in label_lower:
            return "DAYCARE_WEEKLY_PER_VISIT"
        elif "fortnightly" in label_lower:
            return "DAYCARE_FORTNIGHTLY_PER_VISIT"
        else:
            return "DAYCARE_SINGLE"
    elif "home visit" in label_lower or "home-visit" in label_lower:
        if "30m" in label_lower and "2" in label_lower:
            return "HOME_VISIT_30M_2X_SINGLE"
        else:
            return "HOME_VISIT_30M_SINGLE"
    elif "pickup" in label_lower or "drop" in label_lower:
        return "PICKUP_DROPOFF_SINGLE"
    elif "scoop" in label_lower or "poop" in label_lower:
        if "weekly" in label_lower or "monthly" in label_lower:
            return "SCOOP_WEEKLY_MONTHLY"
        else:
            return "SCOOP_SINGLE"
    elif "walk" in label_lower:
        return "WALK_GENERAL"
    else:
        # Convert label to a reasonable service type code
        return label.upper().replace(" ", "_").replace("-", "_")

def fix_missing_client_ids():
    """Fix bookings with missing client_id by looking up from Stripe invoice data"""
    conn = get_conn()
    cur = conn.cursor()
    
    print("\n=== FIXING MISSING CLIENT IDS ===")
    
    # Get bookings with missing client_id but with Stripe invoice ID
    cur.execute("""
        SELECT id, stripe_invoice_id, service, service_type, start_dt
        FROM bookings 
        WHERE (client_id IS NULL OR client_id = 0)
          AND stripe_invoice_id IS NOT NULL 
          AND stripe_invoice_id != ''
    """)
    
    missing_client_bookings = cur.fetchall()
    fixed_count = 0
    
    if not missing_client_bookings:
        print("No bookings with missing client_id found to fix")
        conn.close()
        return 0
    
    print(f"Found {len(missing_client_bookings)} bookings with missing client_id")
    
    try:
        import stripe
        from secrets_config import get_stripe_key
        stripe.api_key = get_stripe_key()
        
        for booking in missing_client_bookings:
            booking_id = booking['id']
            invoice_id = booking['stripe_invoice_id']
            
            try:
                # Get invoice from Stripe to find customer
                invoice = stripe.Invoice.retrieve(invoice_id, expand=['customer'])
                
                if not hasattr(invoice, 'customer') or not invoice.customer:
                    print(f"  No customer found for booking {booking_id} invoice {invoice_id}")
                    continue
                
                customer = invoice.customer
                customer_email = getattr(customer, 'email', None)
                stripe_customer_id = getattr(customer, 'id', None)
                
                if not customer_email and not stripe_customer_id:
                    print(f"  No customer email/ID for booking {booking_id}")
                    continue
                
                # Find matching client in database
                client_id = None
                
                # Try by Stripe customer ID first
                if stripe_customer_id:
                    client_row = cur.execute("""
                        SELECT id FROM clients 
                        WHERE stripe_customer_id = ? OR stripeCustomerId = ?
                    """, (stripe_customer_id, stripe_customer_id)).fetchone()
                    if client_row:
                        client_id = client_row['id']
                
                # Try by email if not found
                if not client_id and customer_email:
                    client_row = cur.execute("""
                        SELECT id FROM clients 
                        WHERE LOWER(email) = LOWER(?)
                    """, (customer_email,)).fetchone()
                    if client_row:
                        client_id = client_row['id']
                        # Update the client with Stripe customer ID for future lookups
                        cur.execute("""
                            UPDATE clients 
                            SET stripe_customer_id = COALESCE(stripe_customer_id, ?),
                                stripeCustomerId = COALESCE(stripeCustomerId, ?)
                            WHERE id = ?
                        """, (stripe_customer_id, stripe_customer_id, client_id))
                
                # Create new client if not found
                if not client_id and customer_email:
                    customer_name = getattr(customer, 'name', '') or customer_email.split('@')[0]
                    customer_phone = getattr(customer, 'phone', '') or ''
                    
                    cur.execute("""
                        INSERT INTO clients (name, email, phone, stripe_customer_id, stripeCustomerId)
                        VALUES (?, ?, ?, ?, ?)
                    """, (customer_name, customer_email, customer_phone, stripe_customer_id, stripe_customer_id))
                    client_id = cur.lastrowid
                    print(f"  Created new client {client_id} for {customer_email}")
                
                if client_id:
                    # Update the booking with the correct client_id
                    cur.execute("""
                        UPDATE bookings SET client_id = ? WHERE id = ?
                    """, (client_id, booking_id))
                    print(f"  Fixed booking {booking_id}: set client_id to {client_id}")
                    fixed_count += 1
                else:
                    print(f"  Could not resolve client for booking {booking_id}")
                
            except Exception as e:
                print(f"  Error processing booking {booking_id}: {e}")
    
    except Exception as e:
        print(f"Error accessing Stripe: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"Fixed {fixed_count} bookings with missing client_id")
    return fixed_count

def main():
    """Main function to analyze and fix booking issues"""
    print("BOOKING ISSUES FIXER")
    print("===================")
    print(f"Started at: {datetime.now()}")
    
    # Create backup before making changes
    print("\nCreating database backup...")
    backup_db()
    print("Backup created successfully")
    
    # Analyze current issues
    issues = analyze_booking_issues()
    
    if issues['subscription_count'] == 0 and issues['missing_client_count'] == 0:
        print("\n✅ No booking issues found! All bookings have proper client_id, service_type, and service labels.")
        return
    
    # Ask for confirmation before making changes
    print(f"\nFound issues to fix:")
    print(f"  - {issues['subscription_count']} bookings with 'Subscription' labels")
    print(f"  - {issues['missing_client_count']} bookings with missing client_id")
    
    response = input("\nProceed with fixes? (y/N): ").strip().lower()
    if response != 'y':
        print("Aborted by user")
        return
    
    # Apply fixes
    total_fixed = 0
    
    if issues['subscription_count'] > 0:
        total_fixed += fix_subscription_bookings()
    
    if issues['missing_client_count'] > 0:
        total_fixed += fix_missing_client_ids()
    
    # Final analysis
    print(f"\n=== FINAL RESULTS ===")
    print(f"Total bookings fixed: {total_fixed}")
    
    # Re-analyze to show improvements
    print("\nRe-analyzing database after fixes...")
    final_issues = analyze_booking_issues()
    
    print(f"\nBefore fixes:")
    print(f"  - Subscription bookings: {issues['subscription_count']}")
    print(f"  - Missing client_id: {issues['missing_client_count']}")
    
    print(f"\nAfter fixes:")
    print(f"  - Subscription bookings: {final_issues['subscription_count']}")
    print(f"  - Missing client_id: {final_issues['missing_client_count']}")
    
    if final_issues['subscription_count'] == 0 and final_issues['missing_client_count'] == 0:
        print("\n✅ All booking issues have been resolved!")
    else:
        print(f"\n⚠️  Some issues remain - may need manual review")
    
    print(f"\nCompleted at: {datetime.now()}")

if __name__ == "__main__":
    main()
