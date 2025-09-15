#!/usr/bin/env python3
"""
Test CRM functionality without GUI components
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

def test_crm_functionality():
    """Test CRM functionality without GUI"""
    try:
        from crm_module import CRMManager, InteractionType, CustomerStatus
        from db import init_db, get_conn
        
        print("✓ CRM modules imported successfully")
        
        # Test database connection
        init_db()
        conn = get_conn()
        crm = CRMManager(conn)
        
        print("✓ Database initialized and CRM manager created")
        
        # Test basic queries
        cur = conn.cursor()
        clients = cur.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        tags = len(crm.get_all_tags())
        interactions = cur.execute("SELECT COUNT(*) FROM customer_interactions").fetchone()[0]
        
        print(f"✓ Database queries working: {clients} clients, {tags} tags, {interactions} interactions")
        
        # Test CRM analytics
        if clients > 0:
            # Get first client for testing
            first_client = cur.execute("SELECT id FROM clients LIMIT 1").fetchone()
            if first_client:
                client_id = first_client["id"]
                analytics = crm.calculate_customer_analytics(client_id)
                print(f"✓ Customer analytics working: Client {client_id} has {analytics.total_bookings} bookings")
        
        # Test customer segmentation
        high_value = crm.get_high_value_customers(min_revenue_cents=5000)  # $50+
        at_risk = crm.get_at_risk_customers()
        follow_ups = crm.get_clients_needing_follow_up()
        
        print(f"✓ Customer segmentation working:")
        print(f"  - High value customers: {len(high_value)}")
        print(f"  - At risk customers: {len(at_risk)}")
        print(f"  - Need follow-up: {len(follow_ups)}")
        
        # Test schema
        tables = cur.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('customer_interactions', 'customer_tags', 'client_tags')
        """).fetchall()
        
        print(f"✓ CRM tables created: {[t['name'] for t in tables]}")
        
        conn.close()
        print("\n🎉 All CRM functionality tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_crm_functionality()
    sys.exit(0 if success else 1)