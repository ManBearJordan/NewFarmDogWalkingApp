#!/usr/bin/env python3
"""
Unit tests for CRM functionality
"""

import unittest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta

from crm_module import CRMManager, InteractionType, CustomerStatus
from db import init_db

class TestCRMFunctionality(unittest.TestCase):
    
    def setUp(self):
        """Set up test database"""
        # Create temporary database file
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        # Initialize database with test data
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
        # Create basic schema
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                address TEXT,
                stripe_customer_id TEXT,
                notes TEXT,
                dogs_count INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active',
                acquisition_date TEXT,
                last_service_date TEXT,
                total_revenue_cents INTEGER DEFAULT 0,
                service_count INTEGER DEFAULT 0,
                credit_cents INTEGER DEFAULT 0
            );
            
            CREATE TABLE bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER REFERENCES clients(id),
                service_type TEXT NOT NULL,
                start_dt TEXT NOT NULL,
                end_dt TEXT NOT NULL,
                start TEXT,
                end TEXT,
                location TEXT,
                dogs_count INTEGER DEFAULT 1,
                dogs INTEGER DEFAULT 1,
                price_cents INTEGER DEFAULT 0,
                notes TEXT,
                status TEXT DEFAULT 'scheduled',
                service_name TEXT,
                stripe_price_id TEXT
            );
        """)
        self.conn.commit()
        
        # Initialize CRM
        self.crm = CRMManager(self.conn)
    
    def tearDown(self):
        """Clean up test database"""
        self.conn.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_crm_schema_creation(self):
        """Test that CRM tables are created correctly"""
        cur = self.conn.cursor()
        
        # Check that CRM tables exist
        tables = cur.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('customer_interactions', 'customer_tags', 'client_tags')
        """).fetchall()
        
        table_names = [t['name'] for t in tables]
        self.assertIn('customer_interactions', table_names)
        self.assertIn('customer_tags', table_names)
        self.assertIn('client_tags', table_names)
    
    def test_default_tags_creation(self):
        """Test that default tags are created"""
        tags = self.crm.get_all_tags()
        self.assertGreaterEqual(len(tags), 8)  # Should have at least 8 default tags
        
        tag_names = [tag.name for tag in tags]
        self.assertIn('VIP Customer', tag_names)
        self.assertIn('New Customer', tag_names)
        self.assertIn('At Risk', tag_names)
    
    def test_add_interaction(self):
        """Test adding customer interactions"""
        # Add a test client
        cur = self.conn.cursor()
        cur.execute("INSERT INTO clients (name, email) VALUES (?, ?)", 
                   ("Test Client", "test@example.com"))
        client_id = cur.lastrowid
        self.conn.commit()
        
        # Add interaction
        interaction_id = self.crm.add_interaction(
            client_id=client_id,
            interaction_type=InteractionType.EMAIL,
            subject="Test Interaction",
            description="This is a test interaction"
        )
        
        self.assertIsNotNone(interaction_id)
        self.assertGreater(interaction_id, 0)
        
        # Verify interaction was added
        interactions = self.crm.get_client_interactions(client_id)
        self.assertEqual(len(interactions), 1)
        self.assertEqual(interactions[0].subject, "Test Interaction")
        self.assertEqual(interactions[0].interaction_type, InteractionType.EMAIL)
    
    def test_customer_tagging(self):
        """Test customer tagging functionality"""
        # Add a test client
        cur = self.conn.cursor()
        cur.execute("INSERT INTO clients (name, email) VALUES (?, ?)", 
                   ("Test Client", "test@example.com"))
        client_id = cur.lastrowid
        self.conn.commit()
        
        # Get a tag to assign
        tags = self.crm.get_all_tags()
        self.assertGreater(len(tags), 0)
        test_tag = tags[0]
        
        # Add tag to client
        success = self.crm.add_tag_to_client(client_id, test_tag.id)
        self.assertTrue(success)
        
        # Verify tag was assigned
        client_tags = self.crm.get_client_tags(client_id)
        self.assertEqual(len(client_tags), 1)
        self.assertEqual(client_tags[0].name, test_tag.name)
        
        # Remove tag
        success = self.crm.remove_tag_from_client(client_id, test_tag.id)
        self.assertTrue(success)
        
        # Verify tag was removed
        client_tags = self.crm.get_client_tags(client_id)
        self.assertEqual(len(client_tags), 0)
    
    def test_customer_analytics(self):
        """Test customer analytics calculations"""
        # Add a test client
        cur = self.conn.cursor()
        cur.execute("INSERT INTO clients (name, email, acquisition_date) VALUES (?, ?, ?)", 
                   ("Test Client", "test@example.com", datetime.now().isoformat()))
        client_id = cur.lastrowid
        
        # Add test bookings
        booking_date = datetime.now() - timedelta(days=10)
        cur.execute("""
            INSERT INTO bookings (client_id, service_type, start_dt, end_dt, start, end, price_cents)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (client_id, "TEST_SERVICE", booking_date.isoformat(), booking_date.isoformat(),
              booking_date.isoformat(), booking_date.isoformat(), 5000))
        
        cur.execute("""
            INSERT INTO bookings (client_id, service_type, start_dt, end_dt, start, end, price_cents)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (client_id, "TEST_SERVICE", booking_date.isoformat(), booking_date.isoformat(),
              booking_date.isoformat(), booking_date.isoformat(), 3000))
        
        self.conn.commit()
        
        # Calculate analytics
        analytics = self.crm.calculate_customer_analytics(client_id)
        
        self.assertEqual(analytics.client_id, client_id)
        self.assertEqual(analytics.total_bookings, 2)
        self.assertEqual(analytics.total_revenue_cents, 8000)  # 5000 + 3000
        self.assertEqual(analytics.average_booking_value_cents, 4000)  # 8000 / 2
    
    def test_high_value_customers(self):
        """Test high value customer identification"""
        # Add test clients with different revenue levels
        cur = self.conn.cursor()
        
        # High value client
        cur.execute("INSERT INTO clients (name, email) VALUES (?, ?)", 
                   ("High Value Client", "high@example.com"))
        high_value_id = cur.lastrowid
        
        # Low value client
        cur.execute("INSERT INTO clients (name, email) VALUES (?, ?)", 
                   ("Low Value Client", "low@example.com"))
        low_value_id = cur.lastrowid
        
        # Add bookings
        booking_date = datetime.now() - timedelta(days=10)
        
        # High value booking
        cur.execute("""
            INSERT INTO bookings (client_id, service_type, start_dt, end_dt, start, end, price_cents)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (high_value_id, "TEST_SERVICE", booking_date.isoformat(), booking_date.isoformat(),
              booking_date.isoformat(), booking_date.isoformat(), 60000))  # $600
        
        # Low value booking
        cur.execute("""
            INSERT INTO bookings (client_id, service_type, start_dt, end_dt, start, end, price_cents)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (low_value_id, "TEST_SERVICE", booking_date.isoformat(), booking_date.isoformat(),
              booking_date.isoformat(), booking_date.isoformat(), 2000))  # $20
        
        self.conn.commit()
        
        # Test high value customer identification
        high_value_customers = self.crm.get_high_value_customers(min_revenue_cents=50000)  # $500+
        
        self.assertEqual(len(high_value_customers), 1)
        self.assertEqual(high_value_customers[0][0], high_value_id)  # client_id
        self.assertEqual(high_value_customers[0][1], "High Value Client")  # name
        self.assertEqual(high_value_customers[0][2], 60000)  # revenue
    
    def test_at_risk_customers(self):
        """Test at-risk customer identification"""
        cur = self.conn.cursor()
        
        # Recent client
        cur.execute("INSERT INTO clients (name, email, status) VALUES (?, ?, ?)", 
                   ("Recent Client", "recent@example.com", "active"))
        recent_id = cur.lastrowid
        
        # At-risk client
        cur.execute("INSERT INTO clients (name, email, status) VALUES (?, ?, ?)", 
                   ("At Risk Client", "atrisk@example.com", "active"))
        at_risk_id = cur.lastrowid
        
        # Add bookings
        recent_date = datetime.now() - timedelta(days=10)  # Recent booking
        old_date = datetime.now() - timedelta(days=90)     # Old booking
        
        # Recent booking
        cur.execute("""
            INSERT INTO bookings (client_id, service_type, start_dt, end_dt, start, end, price_cents)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (recent_id, "TEST_SERVICE", recent_date.isoformat(), recent_date.isoformat(),
              recent_date.isoformat(), recent_date.isoformat(), 3000))
        
        # Old booking
        cur.execute("""
            INSERT INTO bookings (client_id, service_type, start_dt, end_dt, start, end, price_cents)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (at_risk_id, "TEST_SERVICE", old_date.isoformat(), old_date.isoformat(),
              old_date.isoformat(), old_date.isoformat(), 3000))
        
        self.conn.commit()
        
        # Test at-risk customer identification
        at_risk_customers = self.crm.get_at_risk_customers(days_since_last_booking=60)
        
        self.assertEqual(len(at_risk_customers), 1)
        self.assertEqual(at_risk_customers[0][0], at_risk_id)  # client_id
        self.assertEqual(at_risk_customers[0][1], "At Risk Client")  # name
    
    def test_bulk_stats_update(self):
        """Test bulk customer statistics update"""
        # Add test client and bookings
        cur = self.conn.cursor()
        cur.execute("INSERT INTO clients (name, email) VALUES (?, ?)", 
                   ("Test Client", "test@example.com"))
        client_id = cur.lastrowid
        
        booking_date = datetime.now() - timedelta(days=10)
        cur.execute("""
            INSERT INTO bookings (client_id, service_type, start_dt, end_dt, start, end, price_cents)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (client_id, "TEST_SERVICE", booking_date.isoformat(), booking_date.isoformat(),
              booking_date.isoformat(), booking_date.isoformat(), 5000))
        
        self.conn.commit()
        
        # Update bulk stats
        self.crm.bulk_update_customer_stats()
        
        # Verify stats were updated
        client = cur.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        self.assertEqual(client["total_revenue_cents"], 5000)
        self.assertEqual(client["service_count"], 1)
        self.assertIsNotNone(client["last_service_date"])
        self.assertIsNotNone(client["acquisition_date"])

if __name__ == '__main__':
    unittest.main()