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


class ServiceMapTest(TestCase):
    """Test service mapping functionality."""
    
    def test_get_service_code_direct_match(self):
        """Test direct matching of service labels to codes."""
        from .service_map import get_service_code
        
        # Test exact matches
        self.assertEqual(get_service_code("walk"), "walk")
        self.assertEqual(get_service_code("daycare"), "daycare")
        self.assertEqual(get_service_code("home visit"), "home_visit")
        self.assertEqual(get_service_code("poop scoop"), "poop_scoop")
        self.assertEqual(get_service_code("overnight"), "overnight")
        
        # Test case insensitivity
        self.assertEqual(get_service_code("WALK"), "walk")
        self.assertEqual(get_service_code("DayCare"), "daycare")
        self.assertEqual(get_service_code("HOME VISIT"), "home_visit")
    
    def test_get_service_code_fuzzy_match(self):
        """Test fuzzy matching capabilities."""
        from .service_map import get_service_code
        
        # Test partial matches
        self.assertEqual(get_service_code("dog walking"), "walk")
        self.assertEqual(get_service_code("30 min walk"), "walk_30min")
        self.assertEqual(get_service_code("1 hour walking"), "walk_1hr")
        self.assertEqual(get_service_code("quick walking"), "walk_30min")
        
        # Test whitespace handling
        self.assertEqual(get_service_code("  home   visit  "), "home_visit")
        self.assertEqual(get_service_code("day care"), "daycare")
    
    def test_get_service_code_no_match(self):
        """Test behavior when no match is found."""
        from .service_map import get_service_code
        
        self.assertIsNone(get_service_code("nonexistent service"))
        self.assertIsNone(get_service_code(""))
        self.assertIsNone(get_service_code(None))
        self.assertIsNone(get_service_code(123))
    
    def test_get_service_display_name(self):
        """Test reverse lookup of display names from service codes."""
        from .service_map import get_service_display_name
        
        # Test existing mappings
        self.assertEqual(get_service_display_name("walk"), "Walk")
        self.assertEqual(get_service_display_name("daycare"), "Daycare")
        self.assertEqual(get_service_display_name("home_visit"), "Home Visit")
        self.assertEqual(get_service_display_name("poop_scoop"), "Poop Scoop")
        
        # Test case insensitivity
        self.assertEqual(get_service_display_name("WALK"), "Walk")
        self.assertEqual(get_service_display_name("HOME_VISIT"), "Home Visit")
        
        # Test unknown codes (should return formatted version)
        self.assertEqual(get_service_display_name("custom_service"), "Custom Service")
        self.assertEqual(get_service_display_name("unknown"), "Unknown")
    
    def test_get_service_display_name_edge_cases(self):
        """Test edge cases for display name lookup."""
        from .service_map import get_service_display_name
        
        self.assertEqual(get_service_display_name(""), "")
        self.assertEqual(get_service_display_name(None), "")
        self.assertEqual(get_service_display_name(123), "")
    
    def test_resolve_service_fields(self):
        """Test resolving service fields from label or code."""
        from .service_map import resolve_service_fields
        
        # Test with labels
        code, display = resolve_service_fields("walk")
        self.assertEqual(code, "walk")
        self.assertEqual(display, "Walk")
        
        code, display = resolve_service_fields("30 minute walk")
        self.assertEqual(code, "walk_30min")
        self.assertEqual(display, "30 Minute Walk")
        
        code, display = resolve_service_fields("overnight care")
        self.assertEqual(code, "overnight")
        self.assertEqual(display, "Overnight")
        
        # Test with codes (these should be treated as unknown labels first, then as codes)
        code, display = resolve_service_fields("custom_service_code")
        self.assertEqual(code, "custom_service_code")
        self.assertEqual(display, "Custom Service Code")
        
        # Test with existing service code that doesn't have a direct label mapping
        code, display = resolve_service_fields("poop_scoop")
        self.assertEqual(code, "poop_scoop")
        self.assertEqual(display, "Poop Scoop")
    
    def test_resolve_service_fields_edge_cases(self):
        """Test edge cases for resolve_service_fields."""
        from .service_map import resolve_service_fields
        
        code, display = resolve_service_fields("")
        self.assertEqual(code, "")
        self.assertEqual(display, "")
        
        code, display = resolve_service_fields(None)
        self.assertEqual(code, "")
        self.assertEqual(display, "")


class DomainRulesTest(TestCase):
    """Test domain rules functionality."""
    
    def test_is_overnight_positive_cases(self):
        """Test positive cases for overnight detection."""
        from .domain_rules import is_overnight
        
        # Test the acceptance criteria
        self.assertTrue(is_overnight("Overnight Walk"))
        
        # Test various overnight-related labels
        self.assertTrue(is_overnight("overnight"))
        self.assertTrue(is_overnight("Overnight"))
        self.assertTrue(is_overnight("OVERNIGHT"))
        self.assertTrue(is_overnight("overnight care"))
        self.assertTrue(is_overnight("Overnight Care"))
        self.assertTrue(is_overnight("overnight stay"))
        self.assertTrue(is_overnight("overnight boarding"))
        self.assertTrue(is_overnight("late night overnight walk"))
        
        # Test with service codes
        self.assertTrue(is_overnight("overnight_walk"))
        self.assertTrue(is_overnight("overnight_care"))
        self.assertTrue(is_overnight("service_overnight"))
        
        # Test whitespace handling
        self.assertTrue(is_overnight("  overnight  "))
        self.assertTrue(is_overnight("overnight   walk"))
    
    def test_is_overnight_negative_cases(self):
        """Test negative cases for overnight detection."""
        from .domain_rules import is_overnight
        
        # Test regular services
        self.assertFalse(is_overnight("walk"))
        self.assertFalse(is_overnight("daycare"))
        self.assertFalse(is_overnight("home visit"))
        self.assertFalse(is_overnight("poop scoop"))
        self.assertFalse(is_overnight("pickup"))
        self.assertFalse(is_overnight("30 minute walk"))
        self.assertFalse(is_overnight("1 hour walk"))
        self.assertFalse(is_overnight("pack walk"))
        self.assertFalse(is_overnight("weekly walk"))
        
        # Test partial matches that shouldn't match
        self.assertFalse(is_overnight("over"))
        self.assertFalse(is_overnight("night"))
        self.assertFalse(is_overnight("day walk"))
        self.assertFalse(is_overnight("morning walk"))
    
    def test_is_overnight_edge_cases(self):
        """Test edge cases for overnight detection."""
        from .domain_rules import is_overnight
        
        self.assertFalse(is_overnight(""))
        self.assertFalse(is_overnight(None))
        self.assertFalse(is_overnight(123))
        self.assertFalse(is_overnight([]))
    
    def test_service_integration(self):
        """Test integration between service mapping and domain rules."""
        from .service_map import get_service_code, resolve_service_fields
        from .domain_rules import is_overnight
        
        # Test overnight service mapping and detection
        service_code = get_service_code("overnight walk")
        self.assertEqual(service_code, "overnight_walk")
        self.assertTrue(is_overnight("overnight walk"))
        self.assertTrue(is_overnight(service_code))
        
        # Test resolve_service_fields with overnight services
        code, display = resolve_service_fields("overnight care")
        self.assertEqual(code, "overnight")
        self.assertTrue(is_overnight(code))
        self.assertTrue(is_overnight(display))
        
        # Test non-overnight services
        code, display = resolve_service_fields("30 minute walk")
        self.assertEqual(code, "walk_30min") 
        self.assertFalse(is_overnight(code))
        self.assertFalse(is_overnight(display))


class StripeKeyManagerTest(TestCase):
    """Test stripe key manager functionality."""
    
    def setUp(self):
        # Clear any existing StripeSettings
        from .models import StripeSettings
        StripeSettings.objects.all().delete()
    
    def test_get_stripe_key_none_when_empty(self):
        """Test get_stripe_key returns None when no key is configured."""
        from .stripe_key_manager import get_stripe_key
        
        # Ensure no environment variable
        import os
        old_env = os.environ.get('STRIPE_SECRET_KEY')
        if 'STRIPE_SECRET_KEY' in os.environ:
            del os.environ['STRIPE_SECRET_KEY']
        
        try:
            result = get_stripe_key()
            self.assertIsNone(result)
        finally:
            # Restore environment
            if old_env is not None:
                os.environ['STRIPE_SECRET_KEY'] = old_env
    
    def test_get_stripe_key_from_env(self):
        """Test get_stripe_key reads from environment variable first."""
        import os
        from .stripe_key_manager import get_stripe_key
        
        old_env = os.environ.get('STRIPE_SECRET_KEY')
        os.environ['STRIPE_SECRET_KEY'] = 'sk_test_env_key'
        
        try:
            result = get_stripe_key()
            self.assertEqual(result, 'sk_test_env_key')
        finally:
            # Restore environment
            if old_env is not None:
                os.environ['STRIPE_SECRET_KEY'] = old_env
            else:
                if 'STRIPE_SECRET_KEY' in os.environ:
                    del os.environ['STRIPE_SECRET_KEY']
    
    def test_get_stripe_key_from_db(self):
        """Test get_stripe_key falls back to database when env is empty."""
        import os
        from .stripe_key_manager import get_stripe_key
        from .models import StripeSettings
        
        # Ensure no environment variable
        old_env = os.environ.get('STRIPE_SECRET_KEY')
        if 'STRIPE_SECRET_KEY' in os.environ:
            del os.environ['STRIPE_SECRET_KEY']
        
        try:
            # Create DB entry
            StripeSettings.objects.create(
                stripe_secret_key='sk_test_db_key',
                is_live_mode=False
            )
            
            result = get_stripe_key()
            self.assertEqual(result, 'sk_test_db_key')
        finally:
            # Restore environment
            if old_env is not None:
                os.environ['STRIPE_SECRET_KEY'] = old_env
    
    def test_get_key_status_not_configured(self):
        """Test get_key_status returns configured=False when no key."""
        from .stripe_key_manager import get_key_status
        
        # Ensure no key configured
        import os
        old_env = os.environ.get('STRIPE_SECRET_KEY')
        if 'STRIPE_SECRET_KEY' in os.environ:
            del os.environ['STRIPE_SECRET_KEY']
        
        try:
            result = get_key_status()
            self.assertEqual(result, {
                'configured': False,
                'mode': None
            })
        finally:
            if old_env is not None:
                os.environ['STRIPE_SECRET_KEY'] = old_env
    
    def test_get_key_status_test_mode(self):
        """Test get_key_status returns mode='test' for test keys."""
        from .stripe_key_manager import get_key_status
        from .models import StripeSettings
        
        StripeSettings.objects.create(
            stripe_secret_key='sk_test_123456789',
            is_live_mode=False
        )
        
        result = get_key_status()
        self.assertEqual(result, {
            'configured': True,
            'mode': 'test'
        })
    
    def test_get_key_status_live_mode(self):
        """Test get_key_status returns mode='live' for live keys."""
        from .stripe_key_manager import get_key_status
        from .models import StripeSettings
        
        StripeSettings.objects.create(
            stripe_secret_key='sk_live_987654321',
            is_live_mode=True
        )
        
        result = get_key_status()
        self.assertEqual(result, {
            'configured': True,
            'mode': 'live'
        })
    
    def test_update_stripe_key_creates_record(self):
        """Test update_stripe_key creates a new record when none exists."""
        from .stripe_key_manager import update_stripe_key, get_stripe_key
        from .models import StripeSettings
        
        update_stripe_key('sk_test_new_key_123')
        
        # Verify it was saved
        key = get_stripe_key()
        self.assertEqual(key, 'sk_test_new_key_123')
        
        # Verify model fields
        settings = StripeSettings.objects.first()
        self.assertEqual(settings.stripe_secret_key, 'sk_test_new_key_123')
        self.assertFalse(settings.is_live_mode)
    
    def test_update_stripe_key_updates_existing(self):
        """Test update_stripe_key updates existing record."""
        from .stripe_key_manager import update_stripe_key, get_stripe_key
        from .models import StripeSettings
        
        # Create initial record
        StripeSettings.objects.create(
            stripe_secret_key='sk_test_old_key',
            is_live_mode=False
        )
        
        # Update it
        update_stripe_key('sk_live_new_key_456')
        
        # Verify it was updated
        key = get_stripe_key()
        self.assertEqual(key, 'sk_live_new_key_456')
        
        # Verify only one record exists and it's updated
        settings = StripeSettings.objects.get()  # Should not raise MultipleObjectsReturned
        self.assertEqual(settings.stripe_secret_key, 'sk_live_new_key_456')
        self.assertTrue(settings.is_live_mode)
    
    def test_update_stripe_key_validation(self):
        """Test update_stripe_key validates input."""
        from .stripe_key_manager import update_stripe_key
        
        with self.assertRaises(ValueError):
            update_stripe_key("")
        
        with self.assertRaises(ValueError):
            update_stripe_key("   ")
        
        with self.assertRaises(ValueError):
            update_stripe_key(None)