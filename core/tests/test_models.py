import pytest
from django.contrib.auth.models import User
from core.models import Client, Booking, Pet, Tag
from django.utils import timezone

@pytest.mark.django_db
def test_client_str_representation():
    # Test Client model __str__ method
    client = Client.objects.create(name="Test Client")
    assert str(client) == "Test Client"

@pytest.mark.django_db
def test_booking_str_representation():
    # Test Booking model __str__ method
    client = Client.objects.create(name="Test Client")
    booking = Booking.objects.create(
        client=client,
        service_code="walk",
        service_name="Dog Walk",
        start_dt=timezone.now(),
        end_dt=timezone.now(),
        status="confirmed"
    )
    expected = f"Dog Walk for {client.name} on {booking.start_dt.date()}"
    assert str(booking) == expected

@pytest.mark.django_db
def test_pet_str_representation():
    # Test Pet model __str__ method
    client = Client.objects.create(name="Test Client")
    pet = Pet.objects.create(client=client, name="Buddy", breed="Golden Retriever")
    assert str(pet) == "Buddy (Test Client)"

@pytest.mark.django_db
def test_tag_str_representation():
    # Test Tag model __str__ method
    tag = Tag.objects.create(name="VIP")
    assert str(tag) == "VIP"