"""
Tests for delete subscription functionality.

This test suite validates the delete subscription feature that allows users
to delete subscriptions from the local database and clean up associated 
bookings and calendar entries.

IMPORTANT: The delete subscription feature only performs local cleanup.
It does NOT cancel or modify subscriptions in Stripe. Stripe subscriptions
remain active and continue billing after local deletion.
"""

import unittest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Set up path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unified_booking_helpers import delete_subscription_locally
from stripe_integration import cancel_subscription
from db import init_db, get_conn


class TestDeleteSubscription(unittest.TestCase):
    """Test suite for delete subscription functionality.
    
    Note: The delete subscription feature only performs local database cleanup.
    It does NOT cancel subscriptions in Stripe. Stripe subscriptions remain active
    and continue billing after local deletion.
    """
    
    def setUp(self):
        """Set up test database and environment."""
        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        # Mock the DB_PATH in db module
        import db
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.db_path
        
        # Initialize test database
        init_db()
        self.conn = get_conn()
        
        # Create test subscription data
        self._setup_test_data()
    
    def tearDown(self):
        """Clean up test database."""
        self.conn.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)
        
        # Restore original DB_PATH
        import db
        db.DB_PATH = self.original_db_path
    
    def _setup_test_data(self):
        """Set up test subscription, bookings, and schedule data."""
        cur = self.conn.cursor()
        
        # Create test client
        cur.execute("""
            INSERT INTO clients (id, name, email, stripe_customer_id) 
            VALUES (1, 'Test Client', 'test@example.com', 'cus_test123')
        """)
        
        # Create test subscription schedule
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sub_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stripe_subscription_id TEXT UNIQUE NOT NULL,
                days_mask INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                dogs INTEGER NOT NULL DEFAULT 1,
                location TEXT,
                notes TEXT
            )
        """)
        
        cur.execute("""
            INSERT INTO sub_schedules 
            (stripe_subscription_id, days_mask, start_time, end_time, dogs, location, notes)
            VALUES ('sub_test123', 34, '09:00', '10:00', 1, 'Test Location', 'Test notes')
        """)
        
        # Create test bookings
        future_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        past_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        
        cur.execute("""
            INSERT INTO bookings 
            (id, client_id, service_type, start_dt, end_dt, location, dogs, created_from_sub_id, source)
            VALUES 
            (1, 1, 'WALK_GENERAL', ?, '2025-01-25 10:00:00', 'Test Location', 1, 'sub_test123', 'subscription'),
            (2, 1, 'WALK_GENERAL', ?, '2025-01-20 10:00:00', 'Test Location', 1, 'sub_test123', 'subscription')
        """, (future_date, past_date))
        
        # Create test calendar entries
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sub_occurrences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stripe_subscription_id TEXT NOT NULL,
                start_dt TEXT NOT NULL,
                end_dt TEXT NOT NULL,
                dogs INTEGER DEFAULT 1,
                location TEXT,
                active INTEGER DEFAULT 1
            )
        """)
        
        cur.execute("""
            INSERT INTO sub_occurrences 
            (stripe_subscription_id, start_dt, end_dt, dogs, location, active)
            VALUES 
            ('sub_test123', ?, '2025-01-25 10:00:00', 1, 'Test Location', 1),
            ('sub_test123', ?, '2025-01-20 10:00:00', 1, 'Test Location', 1)
        """, (future_date, past_date))
        
        self.conn.commit()
    
    def test_delete_subscription_locally_removes_future_bookings(self):
        """Test that local deletion removes only future bookings."""
        results = delete_subscription_locally(self.conn, 'sub_test123')
        
        # Should delete 1 future booking
        self.assertEqual(results['bookings_deleted'], 1)
        
        # Verify past booking is still there
        cur = self.conn.cursor()
        remaining_bookings = cur.execute("""
            SELECT COUNT(*) FROM bookings 
            WHERE created_from_sub_id = 'sub_test123'
        """).fetchone()[0]
        
        self.assertEqual(remaining_bookings, 1)  # Past booking should remain
    
    def test_delete_subscription_locally_removes_calendar_entries(self):
        """Test that local deletion removes calendar entries."""
        results = delete_subscription_locally(self.conn, 'sub_test123')
        
        # Should delete 1 future calendar entry
        self.assertEqual(results['calendar_entries_deleted'], 1)
        
        # Verify past entry is still there
        cur = self.conn.cursor()
        remaining_entries = cur.execute("""
            SELECT COUNT(*) FROM sub_occurrences 
            WHERE stripe_subscription_id = 'sub_test123'
        """).fetchone()[0]
        
        self.assertEqual(remaining_entries, 1)  # Past entry should remain
    
    def test_delete_subscription_locally_removes_schedule(self):
        """Test that local deletion removes subscription schedule."""
        results = delete_subscription_locally(self.conn, 'sub_test123')
        
        # Should delete 1 schedule entry
        self.assertEqual(results['schedules_deleted'], 1)
        
        # Verify schedule is gone
        cur = self.conn.cursor()
        remaining_schedules = cur.execute("""
            SELECT COUNT(*) FROM sub_schedules 
            WHERE stripe_subscription_id = 'sub_test123'
        """).fetchone()[0]
        
        self.assertEqual(remaining_schedules, 0)
    
    def test_delete_nonexistent_subscription(self):
        """Test deleting a subscription that doesn't exist."""
        results = delete_subscription_locally(self.conn, 'sub_nonexistent')
        
        # Should report 0 deletions
        self.assertEqual(results['bookings_deleted'], 0)
        self.assertEqual(results['calendar_entries_deleted'], 0)
        self.assertEqual(results['schedules_deleted'], 0)
    
    @patch('stripe_integration.stripe')
    def test_cancel_subscription_success(self, mock_stripe):
        """Test successful Stripe subscription cancellation (standalone function, NOT used by delete workflow)."""
        # Mock successful cancellation
        mock_subscription = Mock()
        mock_subscription.status = 'canceled'
        mock_stripe.Subscription.cancel.return_value = mock_subscription
        mock_stripe.Subscription.modify.return_value = mock_subscription
        
        result = cancel_subscription('sub_test123')
        
        self.assertTrue(result)
        mock_stripe.Subscription.modify.assert_called_once_with(
            'sub_test123', cancel_at_period_end=False
        )
        mock_stripe.Subscription.cancel.assert_called_once_with('sub_test123')
    
    @patch('stripe_integration.stripe')
    def test_cancel_subscription_failure(self, mock_stripe):
        """Test Stripe subscription cancellation failure (standalone function, NOT used by delete workflow)."""
        # Mock failure
        mock_stripe.Subscription.cancel.side_effect = Exception("Stripe error")
        
        result = cancel_subscription('sub_test123')
        
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()