from django.test import TestCase, Client as TestClient
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import Client, StripeSubscriptionLink, Service


class SubscriptionAdminTest(TestCase):
    def setUp(self):
        # Create a staff user
        self.staff_user = User.objects.create_user(
            username='admin',
            password='testpass',
            is_staff=True
        )
        self.client_test = TestClient()
        self.client_test.login(username='admin', password='testpass')
        
        # Create a client
        self.dog_client = Client.objects.create(
            name='Test Client',
            email='test@example.com',
            phone='1234567890',
            address='123 Test St',
            status='active'
        )
        
        # Create a service
        self.service = Service.objects.create(
            code='walk30',
            name='30 Min Walk',
            duration_minutes=30,
            is_active=True
        )
        
        # Create a subscription link
        self.sub_link = StripeSubscriptionLink.objects.create(
            stripe_subscription_id='sub_test123',
            client=self.dog_client,
            service_code='walk30',
            status='active'
        )
    
    def test_link_list_requires_staff(self):
        """Test that non-staff users cannot access the link list page."""
        self.client_test.logout()
        response = self.client_test.get(reverse('admin_sub_links'))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
    
    def test_link_list_staff_access(self):
        """Test that staff users can access the link list page."""
        response = self.client_test.get(reverse('admin_sub_links'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Subscription → Service & Time Mapping')
        self.assertContains(response, 'sub_test123')
    
    def test_link_save_updates_fields(self):
        """Test that link_save view correctly updates subscription link fields."""
        url = reverse('admin_sub_link_save', args=[self.sub_link.id])
        response = self.client_test.post(url, {
            'service_code': 'walk30',
            'weekday': '2',  # Wednesday
            'time_of_day': '14:30'
        })
        
        # Should redirect back to the list
        self.assertEqual(response.status_code, 302)
        
        # Check that the fields were updated
        self.sub_link.refresh_from_db()
        self.assertEqual(self.sub_link.service_code, 'walk30')
        self.assertEqual(self.sub_link.weekday, 2)
        self.assertEqual(str(self.sub_link.time_of_day), '14:30:00')
    
    def test_link_save_handles_empty_weekday(self):
        """Test that empty weekday is saved as None."""
        url = reverse('admin_sub_link_save', args=[self.sub_link.id])
        response = self.client_test.post(url, {
            'service_code': 'walk30',
            'weekday': '',
            'time_of_day': '10:00'
        })
        
        self.sub_link.refresh_from_db()
        self.assertIsNone(self.sub_link.weekday)
    
    def test_link_save_handles_empty_time(self):
        """Test that empty time_of_day is saved as None."""
        url = reverse('admin_sub_link_save', args=[self.sub_link.id])
        response = self.client_test.post(url, {
            'service_code': 'walk30',
            'weekday': '1',
            'time_of_day': ''
        })
        
        self.sub_link.refresh_from_db()
        self.assertIsNone(self.sub_link.time_of_day)
    
    def test_link_save_nonexistent_link(self):
        """Test that attempting to save a nonexistent link shows an error."""
        url = reverse('admin_sub_link_save', args=[99999])
        response = self.client_test.post(url, {
            'service_code': 'walk30',
            'weekday': '1',
            'time_of_day': '10:00'
        })
        
        # Should redirect with error message
        self.assertEqual(response.status_code, 302)
        messages = list(response.wsgi_request._messages)
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'Link not found.')
