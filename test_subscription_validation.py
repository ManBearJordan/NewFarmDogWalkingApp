"""
Test the new subscription validation and automatic sync workflow.
"""

import unittest
import sqlite3
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from subscription_validator import (
    get_subscriptions_missing_schedule_data,
    is_subscription_schedule_complete,
    update_local_subscription_schedule
)


class TestSubscriptionValidation(unittest.TestCase):
    """Test subscription validation and missing data detection."""

    def setUp(self):
        """Set up test database."""
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        
        # Create subs_schedule table
        self.conn.execute("""
            CREATE TABLE subs_schedule (
                stripe_subscription_id TEXT PRIMARY KEY,
                days TEXT,
                start_time TEXT,
                end_time TEXT,
                dogs INTEGER,
                location TEXT,
                notes TEXT,
                updated_at TEXT
            )
        """)
        self.conn.commit()

    def tearDown(self):
        """Clean up test database."""
        self.conn.close()

    def test_complete_subscription_validation(self):
        """Test validation of a complete subscription."""
        subscription = {
            'id': 'sub_complete',
            'metadata': {
                'days': 'MON,WED,FRI',
                'start_time': '09:30',
                'end_time': '10:30',
                'location': '123 Test Street, Brisbane',
                'dogs': '2',
                'notes': 'Test notes'
            }
        }
        
        result = is_subscription_schedule_complete(subscription)
        self.assertTrue(result)

    def test_incomplete_subscription_validation(self):
        """Test validation of an incomplete subscription."""
        subscription = {
            'id': 'sub_incomplete',
            'metadata': {
                'days': '',  # Missing days
                'start_time': '09:00',  # Default time
                'end_time': '10:00',    # Default time
                'location': '',         # Missing location
                'dogs': '0'            # Invalid dog count
            }
        }
        
        result = is_subscription_schedule_complete(subscription)
        self.assertFalse(result)

    def test_missing_schedule_data_detection(self):
        """Test detection of subscriptions missing schedule data."""
        subscriptions = [
            {
                'id': 'sub_complete',
                'metadata': {
                    'days': 'MON,WED,FRI',
                    'start_time': '09:30',
                    'end_time': '10:30',
                    'location': '123 Test Street',
                    'dogs': '2'
                }
            },
            {
                'id': 'sub_incomplete',
                'metadata': {
                    'days': '',
                    'start_time': '09:00',
                    'end_time': '10:00',
                    'location': '',
                    'dogs': '1'
                }
            }
        ]
        
        missing_data_subs = get_subscriptions_missing_schedule_data(subscriptions)
        
        # Both subscriptions should be flagged - complete one missing service_code, incomplete one missing multiple fields
        self.assertEqual(len(missing_data_subs), 2)
        
        # Find the incomplete subscription
        incomplete_sub = None
        complete_sub = None
        for sub in missing_data_subs:
            if sub['id'] == 'sub_incomplete':
                incomplete_sub = sub
            elif sub['id'] == 'sub_complete':
                complete_sub = sub
        
        self.assertIsNotNone(incomplete_sub)
        self.assertIsNotNone(complete_sub)
        
        # Complete subscription should only be missing service_code
        self.assertIn('service_code', complete_sub['missing_fields'])
        
        # Incomplete subscription should be missing multiple fields including service_code
        self.assertIn('service_code', incomplete_sub['missing_fields'])
        self.assertIn('days', incomplete_sub['missing_fields'])
        self.assertIn('start_time', incomplete_sub['missing_fields'])
        self.assertIn('end_time', incomplete_sub['missing_fields'])
        self.assertIn('location', incomplete_sub['missing_fields'])

    def test_partial_missing_data(self):
        """Test subscription with some missing fields."""
        subscription = {
            'id': 'sub_partial',
            'metadata': {
                'days': 'TUE,THU',     # Present
                'start_time': '14:00',  # Present
                'end_time': '15:00',    # Present
                'location': '',         # Missing
                'dogs': '3'            # Present
            }
        }
        
        missing_data_subs = get_subscriptions_missing_schedule_data([subscription])
        
        self.assertEqual(len(missing_data_subs), 1)
        # Should be missing both service_code and location  
        self.assertCountEqual(missing_data_subs[0]['missing_fields'], ['service_code', 'location'])

    def test_edge_cases(self):
        """Test edge cases in subscription validation."""
        # Empty subscription list
        result = get_subscriptions_missing_schedule_data([])
        self.assertEqual(len(result), 0)
        
        # Subscription with no metadata
        sub_no_metadata = {'id': 'sub_no_meta'}
        missing = get_subscriptions_missing_schedule_data([sub_no_metadata])
        self.assertEqual(len(missing), 1)
        
        # Subscription with no ID
        sub_no_id = {'metadata': {'days': 'MON'}}
        missing = get_subscriptions_missing_schedule_data([sub_no_id])
        self.assertEqual(len(missing), 0)  # Should skip subscriptions without ID

    def test_local_schedule_update(self):
        """Test updating local subscription schedule."""
        subscription_id = 'sub_test'
        days = 'MON,WED,FRI'
        start_time = '09:30'
        end_time = '10:30'
        location = '123 Test Street'
        dogs = 2
        notes = 'Test notes'
        
        # Update schedule
        result = update_local_subscription_schedule(
            self.conn, subscription_id, days, start_time, end_time, location, dogs, notes
        )
        
        self.assertTrue(result)
        
        # Verify data was saved
        row = self.conn.execute(
            "SELECT * FROM subs_schedule WHERE stripe_subscription_id = ?", 
            (subscription_id,)
        ).fetchone()
        
        self.assertIsNotNone(row)
        self.assertEqual(row['days'], days)
        self.assertEqual(row['start_time'], start_time)
        self.assertEqual(row['end_time'], end_time)
        self.assertEqual(row['location'], location)
        self.assertEqual(row['dogs'], dogs)
        self.assertEqual(row['notes'], notes)

    def test_time_validation_logic(self):
        """Test that default times are considered missing."""
        # Default times should be considered missing
        default_time_sub = {
            'id': 'sub_default',
            'metadata': {
                'days': 'MON',
                'start_time': '09:00',  # Default
                'end_time': '10:00',    # Default
                'location': 'Test Location',
                'dogs': '1'
            }
        }
        
        result = is_subscription_schedule_complete(default_time_sub)
        self.assertFalse(result)
        
        # Custom times should be valid
        custom_time_sub = {
            'id': 'sub_custom',
            'metadata': {
                'days': 'MON',
                'start_time': '08:30',  # Custom
                'end_time': '09:30',    # Custom
                'location': 'Test Location',
                'dogs': '1'
            }
        }
        
        result = is_subscription_schedule_complete(custom_time_sub)
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()