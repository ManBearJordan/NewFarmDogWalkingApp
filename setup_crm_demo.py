#!/usr/bin/env python3
"""
CRM Demo Script - Adds sample data to demonstrate CRM functionality
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from datetime import datetime, timedelta
from crm_module import CRMManager, InteractionType, CustomerStatus
from db import init_db, get_conn

def setup_demo_data():
    """Set up demo data for CRM functionality"""
    
    # Initialize database and CRM
    init_db()
    conn = get_conn()
    crm = CRMManager(conn)
    cur = conn.cursor()
    
    print("Setting up CRM demo data...")
    
    # Add sample clients if they don't exist
    sample_clients = [
        ("John Smith", "john@example.com", "555-0101", "123 Main St", "Regular customer, has 2 dogs"),
        ("Sarah Johnson", "sarah@example.com", "555-0102", "456 Oak Ave", "VIP customer, weekly walks"),
        ("Mike Brown", "mike@example.com", "555-0103", "789 Pine St", "New customer, trial period"),
        ("Lisa Wilson", "lisa@example.com", "555-0104", "321 Elm Dr", "Seasonal customer, vacation walks only"),
        ("David Lee", "david@example.com", "555-0105", "654 Maple Ln", "High maintenance dogs, special care needed")
    ]
    
    client_ids = []
    for name, email, phone, address, notes in sample_clients:
        # Check if client already exists
        existing = cur.execute("SELECT id FROM clients WHERE email = ?", (email,)).fetchone()
        if existing:
            client_ids.append(existing["id"])
            print(f"Client {name} already exists")
        else:
            cur.execute("""
                INSERT INTO clients (name, email, phone, address, notes, status, acquisition_date)
                VALUES (?, ?, ?, ?, ?, 'active', ?)
            """, (name, email, phone, address, notes, datetime.now().isoformat()))
            client_ids.append(cur.lastrowid)
            print(f"Added client: {name}")
    
    conn.commit()
    
    # Add sample bookings to create revenue history
    sample_bookings = [
        (0, "WALK_SHORT_SINGLE", datetime.now() - timedelta(days=30), 3000),  # John - $30
        (0, "WALK_SHORT_SINGLE", datetime.now() - timedelta(days=20), 3000),  # John - $30
        (0, "WALK_LONG_SINGLE", datetime.now() - timedelta(days=10), 4500),   # John - $45
        
        (1, "WALK_SHORT_PACKS", datetime.now() - timedelta(days=25), 5500),   # Sarah - $55
        (1, "WALK_SHORT_PACKS", datetime.now() - timedelta(days=15), 5500),   # Sarah - $55
        (1, "WALK_LONG_PACKS", datetime.now() - timedelta(days=5), 8000),     # Sarah - $80
        
        (2, "HOME_VISIT_30M_SINGLE", datetime.now() - timedelta(days=7), 4000),  # Mike - $40
        
        (3, "DAYCARE_SINGLE", datetime.now() - timedelta(days=90), 7500),     # Lisa - $75
        (3, "DAYCARE_SINGLE", datetime.now() - timedelta(days=60), 7500),     # Lisa - $75
        
        (4, "WALK_SHORT_SINGLE", datetime.now() - timedelta(days=80), 3500),  # David - $35 (old booking, at risk)
    ]
    
    for client_idx, service, booking_date, price_cents in sample_bookings:
        if client_idx < len(client_ids):
            client_id = client_ids[client_idx]
            end_time = booking_date + timedelta(hours=1)
            
            # Check if booking already exists
            existing = cur.execute("""
                SELECT id FROM bookings 
                WHERE client_id = ? AND start_dt = ? AND service_type = ?
            """, (client_id, booking_date.isoformat(), service)).fetchone()
            
            if not existing:
                cur.execute("""
                    INSERT INTO bookings 
                    (client_id, service_type, start_dt, end_dt, start, end, 
                     location, dogs_count, dogs, price_cents, status, service_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?, 'completed', ?)
                """, (client_id, service, booking_date.isoformat(), end_time.isoformat(),
                      booking_date.isoformat(), end_time.isoformat(), 
                      "Customer Home", price_cents, service))
    
    conn.commit()
    
    # Apply appropriate tags to customers
    tag_assignments = [
        (0, "Regular Customer"),  # John
        (1, "VIP Customer"),      # Sarah
        (1, "High Value"),        # Sarah
        (2, "New Customer"),      # Mike
        (3, "Seasonal"),          # Lisa
        (4, "At Risk"),           # David (hasn't booked in a while)
        (4, "Special Needs"),     # David
    ]
    
    # Get tag IDs
    tag_map = {}
    for tag in crm.get_all_tags():
        tag_map[tag.name] = tag.id
    
    for client_idx, tag_name in tag_assignments:
        if client_idx < len(client_ids) and tag_name in tag_map:
            client_id = client_ids[client_idx]
            tag_id = tag_map[tag_name]
            crm.add_tag_to_client(client_id, tag_id)
    
    # Add sample interactions
    sample_interactions = [
        (0, InteractionType.PHONE, "Confirmed weekly walk schedule", "Customer confirmed regular Tuesday walks"),
        (0, InteractionType.EMAIL, "Sent invoice reminder", "Monthly invoice sent via email"),
        
        (1, InteractionType.MEETING, "Discussed additional services", "Customer interested in weekend daycare"),
        (1, InteractionType.PHONE, "Holiday schedule confirmation", "Confirmed extra walks during holidays"),
        
        (2, InteractionType.EMAIL, "Welcome new customer", "Sent welcome package and service information"),
        (2, InteractionType.PHONE, "Follow-up after first service", "Customer very satisfied with first walk"),
        
        (3, InteractionType.EMAIL, "Summer booking inquiry", "Customer asking about July availability"),
        
        (4, InteractionType.SERVICE_ISSUE, "Dog showed aggressive behavior", "Need to discuss safety protocols"),
        (4, InteractionType.FOLLOW_UP, "Check on dog's behavior", "Following up on last incident", True),
    ]
    
    for client_idx, interaction_type, subject, description, *needs_followup in sample_interactions:
        if client_idx < len(client_ids):
            client_id = client_ids[client_idx]
            follow_up_date = None
            if needs_followup and needs_followup[0]:
                follow_up_date = (datetime.now() + timedelta(days=7)).isoformat()
            
            crm.add_interaction(
                client_id=client_id,
                interaction_type=interaction_type,
                subject=subject,
                description=description,
                follow_up_date=follow_up_date,
                created_by="demo_script"
            )
    
    # Update customer statistics
    crm.bulk_update_customer_stats()
    
    # Update specific customer statuses
    if len(client_ids) >= 2:
        crm.update_client_status(client_ids[1], CustomerStatus.VIP)  # Sarah -> VIP
    if len(client_ids) >= 5:
        crm.update_client_status(client_ids[4], CustomerStatus.INACTIVE)  # David -> At Risk
    
    print("Demo data setup complete!")
    print(f"Added/updated {len(client_ids)} clients")
    print(f"Added sample bookings and interactions")
    print(f"Applied customer tags and statuses")
    print("\nYou can now run the app to see the CRM features in action:")
    print("python3 app.py")
    
    # Show some quick stats
    print("\n--- Quick CRM Stats ---")
    total_customers = len(client_ids)
    high_value = crm.get_high_value_customers(min_revenue_cents=10000)  # $100+
    at_risk = crm.get_at_risk_customers()
    follow_ups_needed = crm.get_clients_needing_follow_up()
    
    print(f"Total Customers: {total_customers}")
    print(f"High Value Customers (>$100): {len(high_value)}")
    print(f"At Risk Customers: {len(at_risk)}")
    print(f"Customers Needing Follow-up: {len(follow_ups_needed)}")
    
    conn.close()

if __name__ == "__main__":
    setup_demo_data()