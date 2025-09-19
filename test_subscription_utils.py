#!/usr/bin/env python3
"""
Test script for subscription_utils module focusing on customer resolution
and service type mapping with special characters.
"""

import sqlite3
import tempfile
import os
import sys
from unittest.mock import Mock, patch

# Add the current directory to the path so we can import modules
sys.path.insert(0, '/home/runner/work/NewFarmDogWalkingApp/NewFarmDogWalkingApp')

from subscription_utils import resolve_client_for_subscription, service_type_from_label


def create_test_db():
    """Create a temporary test database with sample clients."""
    db_path = tempfile.mktemp(suffix='.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Create clients table
    conn.execute("""
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            stripe_customer_id TEXT,
            stripeCustomerId TEXT,
            notes TEXT
        )
    """)
    
    # Insert sample clients
    conn.execute("""
        INSERT INTO clients (name, email, stripe_customer_id) 
        VALUES ('John Doe', 'john@example.com', 'cus_test123')
    """)
    
    conn.execute("""
        INSERT INTO clients (name, email, stripeCustomerId) 
        VALUES ('Jane Smith', 'jane@example.com', 'cus_legacy456')
    """)
    
    conn.commit()
    return conn, db_path


def test_resolve_client_for_subscription():
    """Test client resolution with various scenarios."""
    print("=== Testing resolve_client_for_subscription ===")
    
    conn, db_path = create_test_db()
    
    try:
        # Test 1: Existing client by email
        subscription = {
            'id': 'sub_test1',
            'customer': {
                'id': 'cus_new123',
                'email': 'john@example.com'
            }
        }
        
        client_id = resolve_client_for_subscription(conn, subscription)
        print(f"Test 1 (existing email): {client_id}")
        assert client_id == 1, f"Expected client_id 1, got {client_id}"
        print("✅ PASS: Found existing client by email")
        
        # Test 2: Existing client by stripe_customer_id
        subscription = {
            'id': 'sub_test2',
            'customer': {
                'id': 'cus_test123',
                'email': 'different@example.com'
            }
        }
        
        client_id = resolve_client_for_subscription(conn, subscription)
        print(f"Test 2 (existing stripe_customer_id): {client_id}")
        assert client_id == 1, f"Expected client_id 1, got {client_id}"
        print("✅ PASS: Found existing client by stripe_customer_id")
        
        # Test 3: Existing client by legacy stripeCustomerId
        subscription = {
            'id': 'sub_test3',
            'customer': {
                'id': 'cus_legacy456',
                'email': 'another@example.com'
            }
        }
        
        client_id = resolve_client_for_subscription(conn, subscription)
        print(f"Test 3 (legacy stripeCustomerId): {client_id}")
        assert client_id == 2, f"Expected client_id 2, got {client_id}"
        print("✅ PASS: Found existing client by legacy stripeCustomerId")
        
        # Test 4: Create placeholder client when not found
        subscription = {
            'id': 'sub_test4',
            'customer': {
                'id': 'cus_new789',
                'email': 'newclient@example.com'
            }
        }
        
        client_id = resolve_client_for_subscription(conn, subscription)
        print(f"Test 4 (placeholder creation): {client_id}")
        assert client_id is not None and client_id > 2, f"Expected new client_id > 2, got {client_id}"
        
        # Verify placeholder client was created properly
        client = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        assert client['email'] == 'newclient@example.com'
        assert client['stripe_customer_id'] == 'cus_new789'
        assert 'placeholder' in client['notes'].lower()
        print("✅ PASS: Created placeholder client with proper metadata")
        
        # Test 5: Handle subscription with missing email (email-less customer)
        subscription = {
            'id': 'sub_test5',
            'customer': {
                'id': 'cus_noemail'
                # No email field
            }
        }
        
        client_id = resolve_client_for_subscription(conn, subscription)
        print(f"Test 5 (no email): {client_id}")
        assert client_id is not None, "Expected placeholder client creation for no-email customer"
        
        # Verify placeholder name
        client = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        assert 'stripe_customer_' in client['name']
        print("✅ PASS: Created placeholder client for customer without email")
        
    finally:
        conn.close()
        os.unlink(db_path)


def test_service_type_from_label():
    """Test service type mapping with special characters and edge cases."""
    print("\n=== Testing service_type_from_label ===")
    
    test_cases = [
        # Test exact matches from central service map
        ('Short Walk (Single)', 'WALK_SHORT_SINGLE'),
        ('Long Walk (Pack x5)', 'WALK_LONG_PACK5'),
        ('Doggy Daycare (per day)', 'DAYCARE_SINGLE'),
        ('Pick up/Drop off', 'PICKUP_DROPOFF'),
        
        # Test unicode character handling
        ('Dog Walking — Service', 'DOG_WALKING_SERVICE'),  # em dash
        ('Dog Walking – Service', 'DOG_WALKING_SERVICE'),  # en dash
        ('Service × 5 Pack', 'SERVICE_X_5_PACK'),  # multiplication sign
        ('Service • Premium', 'SERVICE_PREMIUM'),  # bullet point
        
        # Test parentheses removal
        ('Walk Service (with extra info)', 'WALK_SERVICE'),
        ('Complex (nested) (parentheses) Service', 'COMPLEX_SERVICE'),
        
        # Test edge cases
        ('', 'UNKNOWN_SERVICE'),
        (None, 'UNKNOWN_SERVICE'),
        ('   ', 'UNKNOWN_SERVICE'),
        ('Special chars: @#$%^&*()', 'SPECIAL_CHARS'),
        
        # Test normalization
        ('áccént sërvìcé', 'ACCENT_SERVICE'),  # diacritics
        ('Mixed   Multiple    Spaces', 'MIXED_MULTIPLE_SPACES'),  # multiple spaces
    ]
    
    passed = 0
    failed = 0
    
    for input_label, expected in test_cases:
        try:
            result = service_type_from_label(input_label)
            if result == expected:
                print(f"✅ PASS: {input_label!r} -> {result}")
                passed += 1
            else:
                print(f"❌ FAIL: {input_label!r} -> {result} (expected {expected})")
                failed += 1
        except Exception as e:
            print(f"❌ ERROR: {input_label!r} -> Exception: {e}")
            failed += 1
    
    print(f"\nService type mapping tests: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✅ All service type mapping tests passed!")
    else:
        print(f"❌ {failed} service type mapping tests failed")


def main():
    """Run all tests."""
    print("🧪 SUBSCRIPTION UTILS TEST SUITE")
    print("=" * 50)
    
    try:
        test_resolve_client_for_subscription()
        test_service_type_from_label()
        
        print("\n" + "=" * 50)
        print("🎯 ALL TESTS COMPLETED")
        
    except Exception as e:
        print(f"\n❌ TEST SUITE FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())