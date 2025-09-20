from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
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


class StripeIntegrationTest(TestCase):
    """Test Stripe integration functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = Client.objects.create(
            name='Test Client',
            email='test@example.com',
            phone='+1234567890',
            address='123 Test St, Test City, TS 12345',
            status='active'
        )

    def test_list_booking_services(self):
        """Test list_booking_services returns static service catalog."""
        from .stripe_integration import list_booking_services
        
        services = list_booking_services()
        
        # Should return 8 services
        self.assertEqual(len(services), 8)
        
        # Check first service structure
        service = services[0]
        expected_keys = {'service_code', 'display_name', 'amount_cents', 'product_id', 'price_id'}
        self.assertEqual(set(service.keys()), expected_keys)
        
        # Check specific values for first service
        self.assertEqual(service['service_code'], 'WALK_30MIN')
        self.assertEqual(service['display_name'], '30 Minute Dog Walk')
        self.assertEqual(service['amount_cents'], 2000)
        self.assertEqual(service['product_id'], 'prod_walk_30min')
        self.assertEqual(service['price_id'], 'price_walk_30min')
        
        # Verify all services have valid data
        for svc in services:
            self.assertIsInstance(svc['service_code'], str)
            self.assertIsInstance(svc['display_name'], str)
            self.assertIsInstance(svc['amount_cents'], int)
            self.assertIsInstance(svc['product_id'], str)
            self.assertIsInstance(svc['price_id'], str)
            self.assertGreater(svc['amount_cents'], 0)

    def test_open_invoice_smart_test_mode(self):
        """Test open_invoice_smart returns correct URL for test mode."""
        from .stripe_integration import open_invoice_smart
        from .models import StripeSettings
        
        # Set up test mode key
        StripeSettings.objects.create(
            stripe_secret_key='sk_test_123456789',
            is_live_mode=False
        )
        
        invoice_id = 'in_test123'
        url = open_invoice_smart(invoice_id)
        
        expected_url = f"https://dashboard.stripe.com/test/invoices/{invoice_id}"
        self.assertEqual(url, expected_url)

    def test_open_invoice_smart_live_mode(self):
        """Test open_invoice_smart returns correct URL for live mode."""
        from .stripe_integration import open_invoice_smart
        from .models import StripeSettings
        
        # Set up live mode key
        StripeSettings.objects.create(
            stripe_secret_key='sk_live_987654321',
            is_live_mode=True
        )
        
        invoice_id = 'in_live123'
        url = open_invoice_smart(invoice_id)
        
        expected_url = f"https://dashboard.stripe.com/invoices/{invoice_id}"
        self.assertEqual(url, expected_url)

    def test_open_invoice_smart_no_key_configured(self):
        """Test open_invoice_smart raises error when no key configured."""
        from .stripe_integration import open_invoice_smart
        
        with self.assertRaises(RuntimeError) as context:
            open_invoice_smart('in_test123')
        
        self.assertIn('Stripe API key not configured', str(context.exception))

    def test_ensure_customer_no_key_configured(self):
        """Test ensure_customer raises error when no key configured."""
        from .stripe_integration import ensure_customer
        
        with self.assertRaises(RuntimeError) as context:
            ensure_customer(self.client)
        
        self.assertIn('Stripe API key not configured', str(context.exception))

    def test_create_or_reuse_draft_invoice_no_key_configured(self):
        """Test create_or_reuse_draft_invoice raises error when no key configured."""
        from .stripe_integration import create_or_reuse_draft_invoice
        
        with self.assertRaises(RuntimeError) as context:
            create_or_reuse_draft_invoice(self.client)
        
        self.assertIn('Stripe API key not configured', str(context.exception))

    def test_push_invoice_items_from_booking_no_key_configured(self):
        """Test push_invoice_items_from_booking raises error when no key configured."""
        from .stripe_integration import push_invoice_items_from_booking
        from datetime import datetime
        from django.utils import timezone
        
        booking = Booking.objects.create(
            client=self.client,
            service_code='WALK_1HR',
            service_name='1 Hour Dog Walk',
            service_label='Standard Walk',
            start_dt=timezone.now(),
            end_dt=timezone.now(),
            location='Test Park',
            price_cents=3500,
            status='confirmed'
        )
        
        with self.assertRaises(RuntimeError) as context:
            push_invoice_items_from_booking(booking, 'in_test123')
        
        self.assertIn('Stripe API key not configured', str(context.exception))


class StripeIntegrationMockedTest(TestCase):
    """Test Stripe integration with mocked Stripe calls."""

    def setUp(self):
        """Set up test data."""
        from .models import StripeSettings
        
        self.client = Client.objects.create(
            name='Test Client',
            email='test@example.com',
            phone='+1234567890',
            address='123 Test St, Test City, TS 12345',
            status='active'
        )
        
        # Set up test Stripe key
        StripeSettings.objects.create(
            stripe_secret_key='sk_test_123456789',
            is_live_mode=False
        )

    def test_ensure_customer_creates_new_customer(self):
        """Test ensure_customer creates new Stripe customer."""
        from unittest.mock import patch, MagicMock
        from .stripe_integration import ensure_customer
        
        # Mock Stripe customer creation
        mock_customer = MagicMock()
        mock_customer.id = 'cus_test123'
        
        with patch('stripe.Customer.list') as mock_list, \
             patch('stripe.Customer.create') as mock_create:
            
            # No existing customers
            mock_list.return_value.data = []
            mock_create.return_value = mock_customer
            
            customer_id = ensure_customer(self.client)
            
            self.assertEqual(customer_id, 'cus_test123')
            self.client.refresh_from_db()
            self.assertEqual(self.client.stripe_customer_id, 'cus_test123')
            
            # Verify create was called with correct parameters
            mock_create.assert_called_once_with(
                email='test@example.com',
                name='Test Client',
                phone='+1234567890',
                metadata={
                    'client_id': str(self.client.id),
                    'source': 'NewFarmDogWalkingApp'
                }
            )

    def test_ensure_customer_finds_existing_customer(self):
        """Test ensure_customer finds existing Stripe customer by email."""
        from unittest.mock import patch, MagicMock
        from .stripe_integration import ensure_customer
        
        # Mock existing customer
        mock_customer = MagicMock()
        mock_customer.id = 'cus_existing123'
        
        with patch('stripe.Customer.list') as mock_list:
            mock_list.return_value.data = [mock_customer]
            
            customer_id = ensure_customer(self.client)
            
            self.assertEqual(customer_id, 'cus_existing123')
            self.client.refresh_from_db()
            self.assertEqual(self.client.stripe_customer_id, 'cus_existing123')

    def test_ensure_customer_updates_from_existing_id(self):
        """Test ensure_customer verifies and normalizes from existing stripe_customer_id."""
        from unittest.mock import patch, MagicMock
        from .stripe_integration import ensure_customer
        
        # Set existing customer ID
        self.client.stripe_customer_id = 'cus_existing456'
        self.client.save()
        
        # Mock Stripe customer with normalized data
        mock_customer = MagicMock()
        mock_customer.id = 'cus_existing456'
        mock_customer.deleted = False
        mock_customer.phone = '+9876543210'  # Different phone
        mock_customer.address = MagicMock()
        mock_customer.address.line1 = '456 Updated St'
        mock_customer.address.line2 = 'Apt 2B'
        mock_customer.address.city = 'Updated City'
        mock_customer.address.state = 'UC'
        mock_customer.address.postal_code = '54321'
        mock_customer.address.country = 'US'
        
        with patch('stripe.Customer.retrieve') as mock_retrieve:
            mock_retrieve.return_value = mock_customer
            
            customer_id = ensure_customer(self.client)
            
            self.assertEqual(customer_id, 'cus_existing456')
            self.client.refresh_from_db()
            
            # Check that phone and address were normalized
            self.assertEqual(self.client.phone, '+9876543210')
            self.assertEqual(self.client.address, '456 Updated St, Apt 2B, Updated City, UC, 54321, US')

    def test_create_or_reuse_draft_invoice_creates_new(self):
        """Test create_or_reuse_draft_invoice creates new draft invoice."""
        from unittest.mock import patch, MagicMock
        from .stripe_integration import create_or_reuse_draft_invoice
        
        # Mock customer creation and invoice creation
        mock_customer = MagicMock()
        mock_customer.id = 'cus_test123'
        mock_invoice = MagicMock()
        mock_invoice.id = 'in_draft123'
        
        with patch('stripe.Customer.list') as mock_customer_list, \
             patch('stripe.Customer.create') as mock_customer_create, \
             patch('stripe.Invoice.list') as mock_invoice_list, \
             patch('stripe.Invoice.create') as mock_invoice_create:
            
            mock_customer_list.return_value.data = []
            mock_customer_create.return_value = mock_customer
            mock_invoice_list.return_value.data = []  # No existing draft
            mock_invoice_create.return_value = mock_invoice
            
            invoice_id = create_or_reuse_draft_invoice(self.client)
            
            self.assertEqual(invoice_id, 'in_draft123')
            
            # Verify invoice create was called
            mock_invoice_create.assert_called_once_with(
                customer='cus_test123',
                auto_advance=False,
                metadata={
                    'client_id': str(self.client.id),
                    'source': 'NewFarmDogWalkingApp'
                }
            )

    def test_create_or_reuse_draft_invoice_reuses_existing(self):
        """Test create_or_reuse_draft_invoice reuses existing draft."""
        from unittest.mock import patch, MagicMock
        from .stripe_integration import create_or_reuse_draft_invoice
        
        # Set existing customer ID
        self.client.stripe_customer_id = 'cus_test123'
        self.client.save()
        
        # Mock existing customer and draft invoice
        mock_customer = MagicMock()
        mock_customer.id = 'cus_test123'
        mock_customer.deleted = False
        mock_customer.phone = None
        mock_customer.address = None
        mock_invoice = MagicMock()
        mock_invoice.id = 'in_existing_draft'
        
        with patch('stripe.Customer.retrieve') as mock_customer_retrieve, \
             patch('stripe.Invoice.list') as mock_invoice_list:
            
            mock_customer_retrieve.return_value = mock_customer
            mock_invoice_list.return_value.data = [mock_invoice]
            
            invoice_id = create_or_reuse_draft_invoice(self.client)
            
            self.assertEqual(invoice_id, 'in_existing_draft')

    def test_push_invoice_items_from_booking(self):
        """Test push_invoice_items_from_booking creates invoice item."""
        from unittest.mock import patch, MagicMock
        from .stripe_integration import push_invoice_items_from_booking
        from django.utils import timezone
        
        # Set up booking and client with Stripe customer ID
        self.client.stripe_customer_id = 'cus_test123'
        self.client.save()
        
        booking = Booking.objects.create(
            client=self.client,
            service_code='WALK_1HR',
            service_name='1 Hour Dog Walk',
            service_label='Standard Walk',
            start_dt=timezone.now(),
            end_dt=timezone.now(),
            location='Test Park',
            price_cents=3500,
            status='confirmed'
        )
        
        with patch('stripe.InvoiceItem.create') as mock_create:
            push_invoice_items_from_booking(booking, 'in_test123')
            
            # Verify invoice item was created with correct parameters
            mock_create.assert_called_once_with(
                customer='cus_test123',
                invoice='in_test123',
                amount=3500,
                currency='usd',
                description=f"1 Hour Dog Walk - {booking.start_dt.strftime('%Y-%m-%d %H:%M')}",
                metadata={
                    'booking_id': str(booking.id),
                    'service_code': 'WALK_1HR',
                    'source': 'NewFarmDogWalkingApp'
                }
            )


class ClientCreditTest(TestCase):
    """Test client credit management functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client.objects.create(
            name='Credit Test Client',
            email='credit@example.com',
            phone='+1234567890',
            address='123 Credit St, Test City, TS 12345',
            credit_cents=1000,  # Start with $10.00 credit
            status='active'
        )
    
    def test_get_client_credit(self):
        """Test get_client_credit returns correct credit amount."""
        from .credit import get_client_credit
        
        credit = get_client_credit(self.client)
        self.assertEqual(credit, 1000)
        
        # Test with zero credit client
        zero_client = Client.objects.create(
            name='Zero Credit Client',
            email='zero@example.com',
            phone='+1234567890',
            address='123 Zero St, Test City, TS 12345',
            status='active'
        )
        
        credit = get_client_credit(zero_client)
        self.assertEqual(credit, 0)
    
    def test_use_client_credit_exact_amount(self):
        """Test using exact credit amount."""
        from .credit import use_client_credit, get_client_credit
        
        # Use exact amount
        use_client_credit(self.client, 1000)
        
        # Verify credit is now zero
        self.client.refresh_from_db()
        self.assertEqual(self.client.credit_cents, 0)
        self.assertEqual(get_client_credit(self.client), 0)
    
    def test_use_client_credit_partial_amount(self):
        """Test using partial credit amount."""
        from .credit import use_client_credit, get_client_credit
        
        # Use partial amount
        use_client_credit(self.client, 300)
        
        # Verify remaining credit
        self.client.refresh_from_db()
        self.assertEqual(self.client.credit_cents, 700)
        self.assertEqual(get_client_credit(self.client), 700)
        
        # Use more partial amount
        use_client_credit(self.client, 200)
        
        # Verify remaining credit
        self.client.refresh_from_db()
        self.assertEqual(self.client.credit_cents, 500)
        self.assertEqual(get_client_credit(self.client), 500)
    
    def test_use_client_credit_zero_amount(self):
        """Test using zero credit amount (no-op)."""
        from .credit import use_client_credit, get_client_credit
        
        original_credit = self.client.credit_cents
        
        # Use zero amount - should be no-op
        use_client_credit(self.client, 0)
        
        # Verify credit unchanged
        self.client.refresh_from_db()
        self.assertEqual(self.client.credit_cents, original_credit)
        self.assertEqual(get_client_credit(self.client), original_credit)
    
    def test_use_client_credit_insufficient_funds(self):
        """Test using more credit than available raises ValidationError."""
        from .credit import use_client_credit
        
        with self.assertRaises(ValidationError) as context:
            use_client_credit(self.client, 1500)  # More than 1000 available
        
        error_message = str(context.exception.message)
        self.assertIn("Insufficient credit", error_message)
        self.assertIn("Available: 1000 cents", error_message)
        self.assertIn("Requested: 1500 cents", error_message)
        
        # Verify credit unchanged
        self.client.refresh_from_db()
        self.assertEqual(self.client.credit_cents, 1000)
    
    def test_use_client_credit_zero_balance(self):
        """Test using credit when client has zero balance."""
        from .credit import use_client_credit
        
        # Create client with zero balance
        zero_client = Client.objects.create(
            name='Zero Balance Client',
            email='zerobal@example.com',
            phone='+1234567890',
            address='123 Zero Balance St, Test City, TS 12345',
            credit_cents=0,
            status='active'
        )
        
        with self.assertRaises(ValidationError) as context:
            use_client_credit(zero_client, 1)
        
        error_message = str(context.exception.message)
        self.assertIn("Insufficient credit", error_message)
        self.assertIn("Available: 0 cents", error_message)
        self.assertIn("Requested: 1 cents", error_message)
    
    def test_use_client_credit_negative_amount_validation(self):
        """Test using negative credit amount raises ValueError."""
        from .credit import use_client_credit
        
        with self.assertRaises(ValueError) as context:
            use_client_credit(self.client, -100)
        
        self.assertEqual(str(context.exception), "amount_cents must be non-negative")
        
        # Verify credit unchanged
        self.client.refresh_from_db()
        self.assertEqual(self.client.credit_cents, 1000)
    
    def test_use_client_credit_non_integer_validation(self):
        """Test using non-integer credit amount raises ValueError."""
        from .credit import use_client_credit
        
        with self.assertRaises(ValueError) as context:
            use_client_credit(self.client, "100")
        
        self.assertEqual(str(context.exception), "amount_cents must be an integer")
        
        with self.assertRaises(ValueError) as context:
            use_client_credit(self.client, 100.5)
        
        self.assertEqual(str(context.exception), "amount_cents must be an integer")
        
        # Verify credit unchanged
        self.client.refresh_from_db()
        self.assertEqual(self.client.credit_cents, 1000)
    
    def test_use_client_credit_atomicity(self):
        """Test that credit operations are atomic and persistent."""
        from .credit import use_client_credit, get_client_credit
        
        # Use credit in multiple operations
        use_client_credit(self.client, 100)
        self.client.refresh_from_db()
        self.assertEqual(self.client.credit_cents, 900)
        
        use_client_credit(self.client, 200)
        self.client.refresh_from_db()
        self.assertEqual(self.client.credit_cents, 700)
        
        # Verify the changes persist
        retrieved_client = Client.objects.get(id=self.client.id)
        self.assertEqual(retrieved_client.credit_cents, 700)
        self.assertEqual(get_client_credit(retrieved_client), 700)
    
    def test_use_client_credit_updates_instance(self):
        """Test that the client instance is updated after credit use."""
        from .credit import use_client_credit
        
        original_credit = self.client.credit_cents
        self.assertEqual(original_credit, 1000)
        
        # Use credit
        use_client_credit(self.client, 300)
        
        # The instance should be updated without refresh_from_db()
        self.assertEqual(self.client.credit_cents, 700)
        
        # Verify database also updated
        db_client = Client.objects.get(id=self.client.id)
        self.assertEqual(db_client.credit_cents, 700)