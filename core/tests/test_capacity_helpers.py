"""Tests for capacity helpers and flexible timetable blocks."""
import pytest
from django.utils import timezone
from datetime import date, time, timedelta
from core.models import ServiceDefaults, TimetableBlock, BlockCapacity, Client, Booking, CapacityHold
from core.capacity_helpers import (
    get_default_duration_minutes,
    list_blocks_for_date,
    block_remaining_capacity,
    create_hold,
)


@pytest.mark.django_db
def test_get_default_duration_minutes():
    """Test retrieving default duration for a service."""
    ServiceDefaults.objects.create(service_code="walk", duration_minutes=60)
    assert get_default_duration_minutes("walk") == 60
    assert get_default_duration_minutes("nonexistent") == 60  # default fallback


@pytest.mark.django_db
def test_list_blocks_for_date():
    """Test listing timetable blocks for a date."""
    today = date.today()
    tb1 = TimetableBlock.objects.create(date=today, start_time=time(9, 0), end_time=time(12, 0), label="Morning")
    tb2 = TimetableBlock.objects.create(date=today, start_time=time(13, 0), end_time=time(16, 0), label="Afternoon")
    
    blocks = list_blocks_for_date(today)
    assert blocks.count() == 2
    assert blocks[0] == tb1
    assert blocks[1] == tb2


@pytest.mark.django_db
def test_block_remaining_capacity():
    """Test calculating remaining capacity for a block."""
    today = date.today()
    block = TimetableBlock.objects.create(date=today, start_time=time(9, 0), end_time=time(12, 0), label="Morning")
    BlockCapacity.objects.create(block=block, service_code="walk", capacity=5)
    
    # Should have full capacity initially
    assert block_remaining_capacity(block, "walk") == 5
    
    # Create a booking that overlaps
    client = Client.objects.create(
        name="Test", email="test@test.com", phone="123", address="addr", status="active"
    )
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(timezone.datetime.combine(today, time(10, 0)), tz)
    end_dt = timezone.make_aware(timezone.datetime.combine(today, time(11, 0)), tz)
    
    Booking.objects.create(
        client=client,
        service_code="walk",
        service_name="Walk",
        service_label="Walk",
        start_dt=start_dt,
        end_dt=end_dt,
        status="active",
        price_cents=2000,
        location="Park",
        deleted=False,
    )
    
    # Should have reduced capacity
    assert block_remaining_capacity(block, "walk") == 4


@pytest.mark.django_db
def test_create_hold_reduces_capacity():
    """Test that creating a hold reduces available capacity."""
    today = date.today()
    block = TimetableBlock.objects.create(date=today, start_time=time(9, 0), end_time=time(12, 0), label="Morning")
    BlockCapacity.objects.create(block=block, service_code="walk", capacity=5)
    
    client = Client.objects.create(
        name="Test", email="test@test.com", phone="123", address="addr", status="active"
    )
    
    # Initial capacity
    assert block_remaining_capacity(block, "walk") == 5
    
    # Create a hold
    hold = create_hold(block, "walk", client)
    assert hold is not None
    
    # Capacity should be reduced
    assert block_remaining_capacity(block, "walk") == 4


@pytest.mark.django_db
def test_expired_holds_dont_affect_capacity():
    """Test that expired holds are purged and don't affect capacity."""
    today = date.today()
    block = TimetableBlock.objects.create(date=today, start_time=time(9, 0), end_time=time(12, 0), label="Morning")
    BlockCapacity.objects.create(block=block, service_code="walk", capacity=5)
    
    client = Client.objects.create(
        name="Test", email="test@test.com", phone="123", address="addr", status="active"
    )
    
    # Create an expired hold
    expired_time = timezone.now() - timedelta(minutes=15)
    CapacityHold.objects.create(
        block=block,
        service_code="walk",
        client=client,
        expires_at=expired_time,
    )
    
    # Capacity should be full (expired hold is purged)
    assert block_remaining_capacity(block, "walk") == 5


@pytest.mark.django_db
def test_no_capacity_when_block_capacity_not_defined():
    """Test that blocks without capacity config return 0."""
    today = date.today()
    block = TimetableBlock.objects.create(date=today, start_time=time(9, 0), end_time=time(12, 0), label="Morning")
    
    # No BlockCapacity created, so should return 0
    assert block_remaining_capacity(block, "walk") == 0
