from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError
from core.models import Client as DogWalkingClient, Subscription
from datetime import time


class SubscriptionAdminTest(TestCase):
    """Test subscription admin interface functionality"""
    
    def setUp(self):
        """Set up test data"""
        # Create a superuser
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )
        
        # Create a client
        self.test_client = DogWalkingClient.objects.create(
            name='Test Client',
            email='test@example.com',
            phone='555-1234'
        )
        
        # Create a subscription
        self.subscription = Subscription.objects.create(
            stripe_subscription_id='sub_test123',
            client=self.test_client,
            status='active',
            service_code='dog_walk_30',
            service_name='30 Minute Dog Walk',
            schedule_days='MON,WED,FRI',
            schedule_start_time=time(10, 0),
            schedule_end_time=time(10, 30),
            schedule_location='123 Main St, Brisbane QLD',
            schedule_dogs=2,
            schedule_notes='Energetic dogs, need firm handling'
        )
        
        # Create Django test client
        self.client = Client()
        self.client.force_login(self.admin_user)
    
    def test_subscription_model_validation(self):
        """Test that subscription validation works correctly"""
        # Test invalid time range
        subscription = Subscription(
            stripe_subscription_id='sub_test456',
            client=self.test_client,
            status='active',
            service_code='dog_walk_30',
            service_name='30 Minute Dog Walk',
            schedule_days='MON,WED,FRI',
            schedule_start_time=time(10, 30),
            schedule_end_time=time(10, 0),  # End before start
            schedule_dogs=1
        )
        
        with self.assertRaises(ValidationError) as cm:
            subscription.clean()
        
        self.assertIn('schedule_end_time', cm.exception.error_dict)
    
    def test_subscription_days_validation(self):
        """Test days validation"""
        # Test invalid day
        subscription = Subscription(
            stripe_subscription_id='sub_test789',
            client=self.test_client,
            status='active',
            service_code='dog_walk_30',
            service_name='30 Minute Dog Walk',
            schedule_days='MON,INVALID,FRI',
            schedule_start_time=time(10, 0),
            schedule_end_time=time(10, 30),
            schedule_dogs=1
        )
        
        with self.assertRaises(ValidationError) as cm:
            subscription.clean()
        
        self.assertIn('schedule_days', cm.exception.error_dict)
    
    def test_subscription_admin_accessible(self):
        """Test that subscription admin page is accessible"""
        url = reverse('admin:core_subscription_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Check that our subscription appears in the list
        self.assertContains(response, 'Test Client')
        self.assertContains(response, '30 Minute Dog Walk')
    
    def test_subscription_admin_change_form(self):
        """Test that subscription change form loads correctly"""
        url = reverse('admin:core_subscription_change', args=[self.subscription.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Check that schedule fields are present and editable
        self.assertContains(response, 'schedule_days')
        self.assertContains(response, 'schedule_start_time')
        self.assertContains(response, 'schedule_end_time')
        self.assertContains(response, 'schedule_location')
        self.assertContains(response, 'schedule_dogs')
        
        # Check for help text
        self.assertContains(response, 'How to update schedules')
        self.assertContains(response, 'Days:')
        self.assertContains(response, 'Use 3-letter codes')
    
    def test_subscription_admin_save(self):
        """Test that subscription can be saved through admin"""
        url = reverse('admin:core_subscription_change', args=[self.subscription.pk])
        
        # Update schedule
        data = {
            'stripe_subscription_id': self.subscription.stripe_subscription_id,
            'client': self.subscription.client.pk,
            'status': self.subscription.status,
            'service_code': self.subscription.service_code,
            'service_name': self.subscription.service_name,
            'schedule_days': 'TUE,THU',  # Changed from MON,WED,FRI
            'schedule_start_time': '14:00',  # Changed from 10:00
            'schedule_end_time': '14:30',   # Changed from 10:30
            'schedule_location': '456 Oak Ave, Brisbane QLD',  # Changed
            'schedule_dogs': 3,  # Changed from 2
            'schedule_notes': 'Updated notes'
        }
        
        response = self.client.post(url, data)
        
        # Should redirect after successful save
        self.assertEqual(response.status_code, 302)
        
        # Verify changes were saved
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.schedule_days, 'TUE,THU')
        self.assertEqual(self.subscription.schedule_start_time, time(14, 0))
        self.assertEqual(self.subscription.schedule_dogs, 3)
        self.assertEqual(self.subscription.schedule_location, '456 Oak Ave, Brisbane QLD')


class ClientAdminTest(TestCase):
    """Test client admin interface"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )
        
        self.test_client_obj = DogWalkingClient.objects.create(
            name='Test Client',
            email='test@example.com',
            phone='555-1234',
            credit_cents=2500  # $25.00
        )
        
        self.client = Client()
        self.client.force_login(self.admin_user)
    
    def test_client_admin_accessible(self):
        """Test that client admin page is accessible"""
        url = reverse('admin:core_client_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Check that credit is displayed in dollars
        self.assertContains(response, '$25.00')


# Create your tests here.
