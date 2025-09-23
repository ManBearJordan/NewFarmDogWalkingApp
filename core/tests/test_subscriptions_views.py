from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from zoneinfo import ZoneInfo
from core.models import SubOccurrence

TZ = ZoneInfo("Australia/Brisbane")


class SubscriptionViewsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.client = Client()
        self.client.login(username="testuser", password="testpass")
    
    def test_subscriptions_list_from_occurrences(self):
        from datetime import timedelta
        now = timezone.now().astimezone(TZ)
        future = now + timedelta(hours=1)
        SubOccurrence.objects.create(stripe_subscription_id="sub_1", start_dt=future, end_dt=future, active=True)
        SubOccurrence.objects.create(stripe_subscription_id="sub_1", start_dt=future, end_dt=future, active=True)
        SubOccurrence.objects.create(stripe_subscription_id="sub_2", start_dt=future, end_dt=future, active=True)
        response = self.client.get(reverse("subscriptions_list"))
        html = response.content.decode()
        self.assertIn("sub_1", html)
        self.assertIn("sub_2", html)
    
    def test_subscriptions_sync_shows_stats(self):
        from unittest.mock import patch
        from core import subscription_sync
        
        with patch.object(subscription_sync, 'sync_subscriptions_to_bookings_and_calendar', return_value={"processed":1,"created":1,"cleaned":0,"errors":0}):
            response = self.client.post(reverse("subscriptions_sync"), follow=True)
            self.assertEqual(response.status_code, 200)
            html = response.content.decode()
            self.assertIn("Sync complete", html)
    
    def test_subscription_delete_cancels_and_cleans(self):
        from unittest.mock import patch
        from datetime import timedelta
        
        # Create occurrences: one past, one future
        now = timezone.now().astimezone(TZ)
        past = now - timedelta(hours=1)   # Past - should NOT be deleted
        future = now + timedelta(hours=1)  # Future - should be deleted
        
        # Create both past and future occurrences for same subscription
        SubOccurrence.objects.create(stripe_subscription_id="sub_X", start_dt=past, end_dt=past, active=True)
        SubOccurrence.objects.create(stripe_subscription_id="sub_X", start_dt=future, end_dt=future, active=True)
        self.assertEqual(SubOccurrence.objects.filter(stripe_subscription_id="sub_X").count(), 2)
        
        with patch('core.views.cancel_subscription_immediately', return_value=None):
            response = self.client.get(reverse("subscription_delete", args=["sub_X"]), follow=True)
            self.assertEqual(response.status_code, 200)
            
            # Should only delete future occurrences, leaving past ones
            remaining_count = SubOccurrence.objects.filter(stripe_subscription_id="sub_X").count()
            self.assertEqual(remaining_count, 1)  # Only the past one should remain
            
            # Verify the remaining one is the past occurrence
            remaining_occ = SubOccurrence.objects.get(stripe_subscription_id="sub_X")
            self.assertEqual(remaining_occ.start_dt, past)