"""
Tests for unified subscription-driven booking and calendar generation.

This test suite validates the new subscription sync functionality that makes
subscriptions the single source of truth for bookings and calendar entries.
"""

import unittest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta, date
from unittest.mock import Mock, patch, MagicMock

# Set up path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from subscription_sync import (
    sync_subscriptions_to_bookings_and_calendar,
    sync_subscription_to_bookings,
    extract_service_code_from_metadata,
    extract_schedule_from_subscription,
    generate_booking_occurrences,
    cleanup_cancelled_subscriptions,
    sync_on_startup
)
from db import init_db, get_conn
from service_map import SERVICE_CODE_TO_DISPLAY


class TestSubscriptionSync(unittest.TestCase):
    """Test suite for subscription sync functionality."""
    
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
        
        # Create test client
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO clients (name, email, stripe_customer_id) 
            VALUES ('Test Client', 'test@example.com', 'cus_test123')
        """)
        self.conn.commit()
        self.test_client_id = cur.lastrowid
        
    def tearDown(self):
        """Clean up test database."""
        self.conn.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)
        
        # Restore original DB_PATH
        import db
        db.DB_PATH = self.original_db_path
    
    def test_extract_service_code_from_metadata(self):
        """Test service code extraction from subscription metadata."""
        # Test direct service_code in metadata
        subscription_data = {
            "metadata": {"service_code": "WALK_SHORT_SINGLE"}
        }
        result = extract_service_code_from_metadata(subscription_data)
        self.assertEqual(result, "WALK_SHORT_SINGLE")
        
        # Test service code from price metadata
        subscription_data = {
            "metadata": {},
            "items": {
                "data": [
                    {
                        "price": {
                            "metadata": {"service_code": "WALK_LONG_SINGLE"}
                        }
                    }
                ]
            }
        }
        result = extract_service_code_from_metadata(subscription_data)
        self.assertEqual(result, "WALK_LONG_SINGLE")
        
        # Test mapping from product name
        subscription_data = {
            "metadata": {},
            "items": {
                "data": [
                    {
                        "price": {
                            "metadata": {},
                            "product": {"name": "Short Walk (Single)"}
                        }
                    }
                ]
            }
        }
        result = extract_service_code_from_metadata(subscription_data)
        self.assertEqual(result, "WALK_SHORT_SINGLE")
        
        # Test no valid service code
        subscription_data = {
            "metadata": {},
            "items": {"data": []}
        }
        result = extract_service_code_from_metadata(subscription_data)
        self.assertIsNone(result)
    
    def test_extract_schedule_from_subscription(self):
        """Test schedule extraction from subscription metadata."""
        subscription_data = {
            "metadata": {
                "days": "MON,WED,FRI",
                "start_time": "08:00",
                "end_time": "09:00",
                "location": "123 Test St",
                "dogs": "2",
                "notes": "Test notes"
            }
        }
        
        schedule = extract_schedule_from_subscription(subscription_data)
        
        self.assertEqual(schedule["days"], "MON,WED,FRI")
        self.assertEqual(schedule["start_time"], "08:00")
        self.assertEqual(schedule["end_time"], "09:00")
        self.assertEqual(schedule["location"], "123 Test St")
        self.assertEqual(schedule["dogs"], 2)
        self.assertEqual(schedule["notes"], "Test notes")
        self.assertEqual(schedule["day_list"], ["MON", "WED", "FRI"])
        
        # Test defaults
        subscription_data = {"metadata": {}}
        schedule = extract_schedule_from_subscription(subscription_data)
        
        self.assertEqual(schedule["start_time"], "09:00")
        self.assertEqual(schedule["end_time"], "10:00")
        self.assertEqual(schedule["dogs"], 0)  # Default is 0 to detect missing dogs for validation
        self.assertEqual(schedule["day_list"], [])
    
    def test_generate_booking_occurrences(self):
        """Test booking occurrence generation."""
        subscription_data = {"id": "sub_test123"}
        schedule = {
            "day_list": ["MON", "WED"],
            "start_time": "09:00",
            "end_time": "10:00",
            "location": "Test Location",
            "dogs": 1,
            "notes": "Test notes"
        }
        
        # Generate occurrences for next 7 days
        occurrences = generate_booking_occurrences(
            subscription_data, self.test_client_id, "WALK_SHORT_SINGLE", 
            schedule, horizon_days=7
        )
        
        # Should have occurrences for Mondays and Wednesdays within 7 days
        self.assertGreater(len(occurrences), 0)
        
        for occurrence in occurrences:
            self.assertEqual(occurrence["subscription_id"], "sub_test123")
            self.assertEqual(occurrence["client_id"], self.test_client_id)
            self.assertEqual(occurrence["service_code"], "WALK_SHORT_SINGLE")
            self.assertEqual(occurrence["location"], "Test Location")
            self.assertEqual(occurrence["dogs"], 1)
            self.assertEqual(occurrence["source"], "subscription")
            
            # Check that start and end times are correct
            start_dt = datetime.strptime(occurrence["start_dt"], "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(occurrence["end_dt"], "%Y-%m-%d %H:%M:%S")
            
            self.assertEqual(start_dt.time().strftime("%H:%M"), "09:00")
            self.assertEqual(end_dt.time().strftime("%H:%M"), "10:00")
            
            # Check day of week is Monday (0) or Wednesday (2)
            self.assertIn(start_dt.weekday(), [0, 2])
    
    @patch('stripe_integration.list_active_subscriptions')
    def test_sync_subscription_to_bookings(self, mock_list_subs):
        """Test syncing a single subscription to bookings."""
        subscription_data = {
            "id": "sub_test123",
            "customer_id": "cus_test123",
            "metadata": {
                "service_code": "WALK_SHORT_SINGLE",
                "days": "MON,WED",
                "start_time": "09:00",
                "end_time": "10:00",
                "location": "Test Location",
                "dogs": "1"
            }
        }
        
        bookings_created = sync_subscription_to_bookings(self.conn, subscription_data)
        
        # Should have created some bookings
        self.assertGreater(bookings_created, 0)
        
        # Check bookings were created in database
        cur = self.conn.cursor()
        bookings = cur.execute("""
            SELECT * FROM bookings 
            WHERE created_from_sub_id = ?
        """, ("sub_test123",)).fetchall()
        
        self.assertGreater(len(bookings), 0)
        
        for booking in bookings:
            self.assertEqual(booking["client_id"], self.test_client_id)
            self.assertEqual(booking["service_type"], "WALK_SHORT_SINGLE")
            self.assertEqual(booking["created_from_sub_id"], "sub_test123")
            self.assertEqual(booking["source"], "subscription")
            self.assertEqual(booking["location"], "Test Location")
    
    @patch('stripe_integration.list_active_subscriptions')
    def test_cleanup_cancelled_subscriptions(self, mock_list_subs):
        """Test cleanup of bookings from cancelled subscriptions."""
        # Create some subscription bookings
        cur = self.conn.cursor()
        future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        
        cur.execute("""
            INSERT INTO bookings 
            (client_id, service_type, start_dt, end_dt, created_from_sub_id, source, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            self.test_client_id, "WALK_SHORT_SINGLE", future_date, future_date,
            "sub_cancelled", "subscription", "scheduled"
        ))
        
        cur.execute("""
            INSERT INTO bookings 
            (client_id, service_type, start_dt, end_dt, created_from_sub_id, source, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            self.test_client_id, "WALK_LONG_SINGLE", future_date, future_date,
            "sub_active", "subscription", "scheduled"
        ))
        
        self.conn.commit()
        
        # Clean up with only sub_active as active
        cleaned = cleanup_cancelled_subscriptions(self.conn, ["sub_active"])
        
        self.assertEqual(cleaned, 1)  # Should clean up sub_cancelled
        
        # Check that only active subscription booking remains
        remaining = cur.execute("""
            SELECT created_from_sub_id FROM bookings 
            WHERE source = 'subscription'
        """).fetchall()
        
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["created_from_sub_id"], "sub_active")
    
    @patch('stripe_integration.list_active_subscriptions')
    def test_full_sync_process(self, mock_list_subs):
        """Test the complete subscription sync process."""
        # Mock Stripe response
        mock_list_subs.return_value = [
            {
                "id": "sub_test123",
                "customer_id": "cus_test123",
                "metadata": {
                    "service_code": "WALK_SHORT_SINGLE",
                    "days": "MON,WED",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "location": "Test Location"
                }
            },
            {
                "id": "sub_test456",
                "customer_id": "cus_test123",
                "metadata": {
                    "service_code": "WALK_LONG_SINGLE",
                    "days": "TUE,THU",
                    "start_time": "14:00",
                    "end_time": "15:30",
                    "location": "Another Location"
                }
            }
        ]
        
        # Run the full sync
        stats = sync_subscriptions_to_bookings_and_calendar(self.conn, horizon_days=14)
        
        # Check stats
        self.assertEqual(stats["subscriptions_processed"], 2)
        self.assertGreater(stats["bookings_created"], 0)
        
        # Check bookings were created
        cur = self.conn.cursor()
        bookings = cur.execute("""
            SELECT created_from_sub_id, service_type, location, COUNT(*) as count
            FROM bookings 
            WHERE source = 'subscription'
            GROUP BY created_from_sub_id, service_type, location
        """).fetchall()
        
        # Should have bookings for both subscriptions
        booking_map = {b["created_from_sub_id"]: b for b in bookings}
        
        self.assertIn("sub_test123", booking_map)
        self.assertIn("sub_test456", booking_map)
        
        self.assertEqual(booking_map["sub_test123"]["service_type"], "WALK_SHORT_SINGLE")
        self.assertEqual(booking_map["sub_test456"]["service_type"], "WALK_LONG_SINGLE")
        
        # Check subscription schedules were updated
        schedules = cur.execute("""
            SELECT stripe_subscription_id, days, start_time, end_time, location
            FROM subs_schedule
        """).fetchall()
        
        self.assertEqual(len(schedules), 2)
        
        schedule_map = {s["stripe_subscription_id"]: s for s in schedules}
        
        self.assertEqual(schedule_map["sub_test123"]["days"], "MON,WED")
        self.assertEqual(schedule_map["sub_test123"]["start_time"], "09:00")
        self.assertEqual(schedule_map["sub_test456"]["days"], "TUE,THU")
        self.assertEqual(schedule_map["sub_test456"]["start_time"], "14:00")
    
    @patch('stripe_integration.list_active_subscriptions')
    def test_startup_sync(self, mock_list_subs):
        """Test startup sync functionality."""
        mock_list_subs.return_value = [
            {
                "id": "sub_startup",
                "customer_id": "cus_test123",
                "metadata": {
                    "service_code": "DAYCARE_SINGLE",
                    "days": "MON,TUE,WED,THU,FRI",
                    "start_time": "07:00",
                    "end_time": "17:00",
                    "location": "Daycare Center"
                }
            }
        ]
        
        stats = sync_on_startup(self.conn)
        
        self.assertEqual(stats["subscriptions_processed"], 1)
        self.assertGreater(stats["bookings_created"], 0)
        
        # Check that horizon is longer for startup (120 days)
        cur = self.conn.cursor()
        future_bookings = cur.execute("""
            SELECT COUNT(*) as count FROM bookings 
            WHERE created_from_sub_id = 'sub_startup'
            AND start_dt > date('now', '+30 days')
        """).fetchone()
        
        # Should have bookings more than 30 days out due to 120-day horizon
        self.assertGreater(future_bookings["count"], 0)
    
    def test_invalid_subscription_data(self):
        """Test handling of invalid subscription data."""
        # No customer ID
        subscription_data = {
            "id": "sub_invalid",
            "metadata": {"service_code": "WALK_SHORT_SINGLE"}
        }
        
        result = sync_subscription_to_bookings(self.conn, subscription_data)
        self.assertEqual(result, 0)
        
        # Invalid service code
        subscription_data = {
            "id": "sub_invalid",
            "customer_id": "cus_test123",
            "metadata": {"service_code": "INVALID_CODE"}
        }
        
        result = sync_subscription_to_bookings(self.conn, subscription_data)
        self.assertEqual(result, 0)
        
        # No schedule days
        subscription_data = {
            "id": "sub_invalid",
            "customer_id": "cus_test123",
            "metadata": {
                "service_code": "WALK_SHORT_SINGLE",
                "days": ""
            }
        }
        
        result = sync_subscription_to_bookings(self.conn, subscription_data)
        self.assertEqual(result, 0)
    
    def test_booking_update_on_resync(self):
        """Test that existing bookings are updated when subscription changes."""
        # Create initial booking
        subscription_data = {
            "id": "sub_update_test",
            "customer_id": "cus_test123",
            "metadata": {
                "service_code": "WALK_SHORT_SINGLE",
                "days": "MON",
                "start_time": "09:00",
                "end_time": "10:00",
                "location": "Original Location"
            }
        }
        
        sync_subscription_to_bookings(self.conn, subscription_data)
        
        # Check initial booking
        cur = self.conn.cursor()
        original_booking = cur.execute("""
            SELECT * FROM bookings 
            WHERE created_from_sub_id = ?
            LIMIT 1
        """, ("sub_update_test",)).fetchone()
        
        self.assertEqual(original_booking["location"], "Original Location")
        
        # Update subscription
        subscription_data["metadata"]["location"] = "Updated Location"
        subscription_data["metadata"]["end_time"] = "10:30"
        
        sync_subscription_to_bookings(self.conn, subscription_data)
        
        # Check updated booking
        updated_booking = cur.execute("""
            SELECT * FROM bookings 
            WHERE created_from_sub_id = ? AND id = ?
        """, ("sub_update_test", original_booking["id"])).fetchone()
        
        self.assertEqual(updated_booking["location"], "Updated Location")
        # Note: end_dt update logic would need to be implemented in sync_subscription_to_bookings


if __name__ == "__main__":
    # Create a test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSubscriptionSync)
    
    # Run with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with error code if tests failed
    import sys
    sys.exit(0 if result.wasSuccessful() else 1)