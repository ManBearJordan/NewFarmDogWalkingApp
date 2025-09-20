from django.test import TestCase
from django.utils import timezone
from datetime import datetime, timedelta
from .models import StripeSettings, Client, Pet, Booking, BookingPet, AdminEvent, SubOccurrence


class StripeSettingsModelTest(TestCase):
    def test_create_and_read_stripe_settings(self):
        """Test creating and reading StripeSettings model."""
        settings = StripeSettings.objects.create(
            stripe_secret_key='sk_test_123456789',
            is_live_mode=False
        )
        
        self.assertEqual(str(settings), "Stripe Settings (Test)")
        self.assertEqual(settings.stripe_secret_key, 'sk_test_123456789')
        self.assertFalse(settings.is_live_mode)
        
        # Test reading
        retrieved_settings = StripeSettings.objects.get(id=settings.id)
        self.assertEqual(retrieved_settings.stripe_secret_key, 'sk_test_123456789')


class ClientModelTest(TestCase):
    def test_create_and_read_client(self):
        """Test creating and reading Client model."""
        client = Client.objects.create(
            name='John Doe',
            email='john.doe@example.com',
            phone='+1234567890',
            address='123 Main St, Anytown, USA',
            notes='Regular customer',
            credit_cents=500,
            status='active',
            stripe_customer_id='cus_123456789'
        )
        
        self.assertEqual(str(client), 'John Doe')
        self.assertEqual(client.name, 'John Doe')
        self.assertEqual(client.email, 'john.doe@example.com')
        self.assertEqual(client.phone, '+1234567890')
        self.assertEqual(client.address, '123 Main St, Anytown, USA')
        self.assertEqual(client.notes, 'Regular customer')
        self.assertEqual(client.credit_cents, 500)
        self.assertEqual(client.status, 'active')
        self.assertEqual(client.stripe_customer_id, 'cus_123456789')
        
        # Test reading
        retrieved_client = Client.objects.get(id=client.id)
        self.assertEqual(retrieved_client.name, 'John Doe')


class PetModelTest(TestCase):
    def setUp(self):
        self.client = Client.objects.create(
            name='Jane Smith',
            email='jane.smith@example.com',
            phone='+0987654321',
            address='456 Oak Ave, Somewhere, USA',
            status='active'
        )
    
    def test_create_and_read_pet(self):
        """Test creating and reading Pet model."""
        pet = Pet.objects.create(
            client=self.client,
            name='Buddy',
            species='dog',
            breed='Golden Retriever',
            meds='None currently',
            behaviour='Friendly and energetic'
        )
        
        self.assertEqual(str(pet), 'Buddy (Jane Smith)')
        self.assertEqual(pet.client, self.client)
        self.assertEqual(pet.name, 'Buddy')
        self.assertEqual(pet.species, 'dog')
        self.assertEqual(pet.breed, 'Golden Retriever')
        self.assertEqual(pet.meds, 'None currently')
        self.assertEqual(pet.behaviour, 'Friendly and energetic')
        
        # Test reading
        retrieved_pet = Pet.objects.get(id=pet.id)
        self.assertEqual(retrieved_pet.name, 'Buddy')
        self.assertEqual(retrieved_pet.client.name, 'Jane Smith')


class BookingModelTest(TestCase):
    def setUp(self):
        self.client = Client.objects.create(
            name='Bob Wilson',
            email='bob.wilson@example.com',
            phone='+1122334455',
            address='789 Pine St, Elsewhere, USA',
            status='active'
        )
    
    def test_create_and_read_booking(self):
        """Test creating and reading Booking model."""
        start_time = timezone.now()
        end_time = start_time + timedelta(hours=1)
        
        booking = Booking.objects.create(
            client=self.client,
            service_code='WALK_1HR',
            service_name='1 Hour Dog Walk',
            service_label='Standard Walk',
            start_dt=start_time,
            end_dt=end_time,
            location='Downtown Park',
            dogs=2,
            status='confirmed',
            price_cents=2500,
            notes='Two dogs, both well-behaved',
            stripe_invoice_id='in_123456789',
            deleted=False
        )
        
        expected_str = f"1 Hour Dog Walk for Bob Wilson on {start_time.date()}"
        self.assertEqual(str(booking), expected_str)
        self.assertEqual(booking.client, self.client)
        self.assertEqual(booking.service_code, 'WALK_1HR')
        self.assertEqual(booking.service_name, '1 Hour Dog Walk')
        self.assertEqual(booking.service_label, 'Standard Walk')
        self.assertEqual(booking.start_dt, start_time)
        self.assertEqual(booking.end_dt, end_time)
        self.assertEqual(booking.location, 'Downtown Park')
        self.assertEqual(booking.dogs, 2)
        self.assertEqual(booking.status, 'confirmed')
        self.assertEqual(booking.price_cents, 2500)
        self.assertEqual(booking.notes, 'Two dogs, both well-behaved')
        self.assertEqual(booking.stripe_invoice_id, 'in_123456789')
        self.assertFalse(booking.deleted)
        
        # Test reading
        retrieved_booking = Booking.objects.get(id=booking.id)
        self.assertEqual(retrieved_booking.service_name, '1 Hour Dog Walk')


class BookingPetModelTest(TestCase):
    def setUp(self):
        self.client = Client.objects.create(
            name='Alice Green',
            email='alice.green@example.com',
            phone='+1555666777',
            address='321 Elm St, Nowhere, USA',
            status='active'
        )
        
        self.pet = Pet.objects.create(
            client=self.client,
            name='Max',
            species='dog',
            breed='Labrador'
        )
        
        start_time = timezone.now()
        end_time = start_time + timedelta(hours=1)
        
        self.booking = Booking.objects.create(
            client=self.client,
            service_code='WALK_30MIN',
            service_name='30 Minute Walk',
            service_label='Quick Walk',
            start_dt=start_time,
            end_dt=end_time,
            location='Neighborhood',
            status='pending'
        )
    
    def test_create_and_read_booking_pet(self):
        """Test creating and reading BookingPet model."""
        booking_pet = BookingPet.objects.create(
            booking=self.booking,
            pet=self.pet
        )
        
        expected_str = f"Max in 30 Minute Walk for Alice Green on {self.booking.start_dt.date()}"
        self.assertEqual(str(booking_pet), expected_str)
        self.assertEqual(booking_pet.booking, self.booking)
        self.assertEqual(booking_pet.pet, self.pet)
        
        # Test reading
        retrieved_booking_pet = BookingPet.objects.get(id=booking_pet.id)
        self.assertEqual(retrieved_booking_pet.pet.name, 'Max')
        self.assertEqual(retrieved_booking_pet.booking.service_name, '30 Minute Walk')


class AdminEventModelTest(TestCase):
    def test_create_and_read_admin_event(self):
        """Test creating and reading AdminEvent model."""
        due_time = timezone.now() + timedelta(days=3)
        
        event = AdminEvent.objects.create(
            due_dt=due_time,
            title='Follow up with new client',
            notes='Call to check satisfaction after first service'
        )
        
        expected_str = f"Follow up with new client (due {due_time.date()})"
        self.assertEqual(str(event), expected_str)
        self.assertEqual(event.due_dt, due_time)
        self.assertEqual(event.title, 'Follow up with new client')
        self.assertEqual(event.notes, 'Call to check satisfaction after first service')
        
        # Test reading
        retrieved_event = AdminEvent.objects.get(id=event.id)
        self.assertEqual(retrieved_event.title, 'Follow up with new client')


class SubOccurrenceModelTest(TestCase):
    def test_create_and_read_sub_occurrence(self):
        """Test creating and reading SubOccurrence model."""
        start_time = timezone.now()
        end_time = start_time + timedelta(days=30)
        
        sub = SubOccurrence.objects.create(
            stripe_subscription_id='sub_123456789',
            start_dt=start_time,
            end_dt=end_time,
            active=True
        )
        
        expected_str = f"Sub sub_123456789 ({start_time.date()} - {end_time.date()})"
        self.assertEqual(str(sub), expected_str)
        self.assertEqual(sub.stripe_subscription_id, 'sub_123456789')
        self.assertEqual(sub.start_dt, start_time)
        self.assertEqual(sub.end_dt, end_time)
        self.assertTrue(sub.active)
        
        # Test reading
        retrieved_sub = SubOccurrence.objects.get(id=sub.id)
        self.assertEqual(retrieved_sub.stripe_subscription_id, 'sub_123456789')
        self.assertTrue(retrieved_sub.active)