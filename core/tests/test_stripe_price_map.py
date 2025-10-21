"""
Tests for StripePriceMap feature (PR15)
"""
from django.test import TestCase
from django.contrib.auth.models import User
from core.models import Service, StripePriceMap, Client, Booking
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


class StripePriceMapModelTest(TestCase):
    """Test the StripePriceMap model"""
    
    def setUp(self):
        self.service = Service.objects.create(
            code="walk30",
            name="30 min walk",
            duration_minutes=30,
            is_active=True
        )
    
    def test_create_price_map(self):
        """Test creating a price map"""
        price_map = StripePriceMap.objects.create(
            price_id="price_123abc",
            product_id="prod_abc123",
            nickname="30min Walk",
            service=self.service,
            active=True
        )
        self.assertEqual(price_map.price_id, "price_123abc")
        self.assertEqual(price_map.service, self.service)
        self.assertTrue(price_map.active)
    
    def test_price_id_unique(self):
        """Test that price_id must be unique"""
        StripePriceMap.objects.create(
            price_id="price_123",
            service=self.service
        )
        with self.assertRaises(Exception):
            StripePriceMap.objects.create(
                price_id="price_123",
                service=self.service
            )
    
    def test_str_representation(self):
        """Test string representation"""
        price_map = StripePriceMap.objects.create(
            price_id="price_test",
            service=self.service
        )
        self.assertEqual(str(price_map), "price_test → walk30")
    
    def test_ordering(self):
        """Test that price maps are ordered by price_id"""
        pm1 = StripePriceMap.objects.create(
            price_id="price_zzz",
            service=self.service
        )
        pm2 = StripePriceMap.objects.create(
            price_id="price_aaa",
            service=self.service
        )
        price_maps = list(StripePriceMap.objects.all())
        self.assertEqual(price_maps[0], pm2)
        self.assertEqual(price_maps[1], pm1)


class ServiceFromLineTest(TestCase):
    """Test the _service_from_line helper function"""
    
    def setUp(self):
        self.service_walk30 = Service.objects.create(
            code="walk30",
            name="30 min walk",
            duration_minutes=30,
            is_active=True
        )
        self.service_walk60 = Service.objects.create(
            code="walk60",
            name="60 min walk",
            duration_minutes=60,
            is_active=True
        )
        self.price_map = StripePriceMap.objects.create(
            price_id="price_mapped_123",
            product_id="prod_123",
            service=self.service_walk30,
            active=True
        )
    
    def test_service_from_mapped_price(self):
        """Test that service is resolved from price mapping"""
        from core.stripe_invoices_sync import _service_from_line
        
        # Mock line item with mapped price
        class MockPrice:
            id = "price_mapped_123"
        
        class MockLine:
            price = MockPrice()
        
        line = MockLine()
        md = {}
        
        service = _service_from_line(line, md)
        self.assertEqual(service, self.service_walk30)
    
    def test_service_from_metadata_fallback(self):
        """Test fallback to metadata.service_code when price not mapped"""
        from core.stripe_invoices_sync import _service_from_line
        
        # Mock line item without mapped price
        class MockPrice:
            id = "price_unmapped_999"
        
        class MockLine:
            price = MockPrice()
        
        line = MockLine()
        md = {"service_code": "walk60"}
        
        service = _service_from_line(line, md)
        self.assertEqual(service, self.service_walk60)
    
    def test_service_not_found(self):
        """Test when service cannot be resolved"""
        from core.stripe_invoices_sync import _service_from_line
        
        class MockPrice:
            id = "price_unmapped_999"
        
        class MockLine:
            price = MockPrice()
        
        line = MockLine()
        md = {"service_code": "nonexistent"}
        
        service = _service_from_line(line, md)
        self.assertIsNone(service)
    
    def test_inactive_price_map_ignored(self):
        """Test that inactive price maps are ignored"""
        from core.stripe_invoices_sync import _service_from_line
        
        # Create inactive price map
        StripePriceMap.objects.create(
            price_id="price_inactive",
            service=self.service_walk60,
            active=False
        )
        
        class MockPrice:
            id = "price_inactive"
        
        class MockLine:
            price = MockPrice()
        
        line = MockLine()
        md = {}
        
        service = _service_from_line(line, md)
        self.assertIsNone(service)
    
    def test_inactive_service_ignored(self):
        """Test that inactive services are ignored"""
        from core.stripe_invoices_sync import _service_from_line
        
        inactive_service = Service.objects.create(
            code="walk90",
            name="90 min walk",
            duration_minutes=90,
            is_active=False
        )
        StripePriceMap.objects.create(
            price_id="price_inactive_svc",
            service=inactive_service,
            active=True
        )
        
        class MockPrice:
            id = "price_inactive_svc"
        
        class MockLine:
            price = MockPrice()
        
        line = MockLine()
        md = {}
        
        service = _service_from_line(line, md)
        self.assertIsNone(service)


class ReconcileIntegrationTest(TestCase):
    """Test reconcile_create_from_line with price mapping"""
    
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin",
            email="admin@test.com",
            password="testpass123"
        )
        self.client_obj = Client.objects.create(
            name="Test Client",
            email="client@test.com",
            phone="1234567890",
            address="123 Test St",
            status="active",
            stripe_customer_id="cus_test123"
        )
        self.service = Service.objects.create(
            code="walk30",
            name="30 min walk",
            duration_minutes=30,
            is_active=True
        )
        self.price_map = StripePriceMap.objects.create(
            price_id="price_test_reconcile",
            service=self.service,
            active=True
        )
    
    def test_admin_registration(self):
        """Test that StripePriceMap is registered in admin"""
        from django.contrib import admin
        from core.models import StripePriceMap
        
        self.assertTrue(admin.site.is_registered(StripePriceMap))
