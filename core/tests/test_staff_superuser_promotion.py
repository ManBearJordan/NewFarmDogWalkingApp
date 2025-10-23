import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
def test_staff_promoted_to_superuser_on_login():
    """Test that staff users are automatically promoted to superuser on login"""
    # Create a staff user who is not a superuser
    user = User.objects.create_user(
        username="staffuser",
        password="testpass123",
        is_staff=True,
        is_superuser=False
    )
    
    # Verify initial state
    assert user.is_staff is True
    assert user.is_superuser is False
    
    # Login the user (this should trigger the signal)
    client = Client()
    response = client.post(reverse("login"), {
        "username": "staffuser",
        "password": "testpass123"
    })
    
    # Refresh user from database
    user.refresh_from_db()
    
    # Verify the user is now a superuser
    assert user.is_superuser is True
    assert user.is_staff is True


@pytest.mark.django_db
def test_non_staff_user_not_promoted():
    """Test that non-staff users are not promoted to superuser"""
    # Create a regular user (not staff)
    user = User.objects.create_user(
        username="regularuser",
        password="testpass123",
        is_staff=False,
        is_superuser=False
    )
    
    # Verify initial state
    assert user.is_staff is False
    assert user.is_superuser is False
    
    # Login the user
    client = Client()
    response = client.post(reverse("login"), {
        "username": "regularuser",
        "password": "testpass123"
    })
    
    # Refresh user from database
    user.refresh_from_db()
    
    # Verify the user is still not a superuser
    assert user.is_superuser is False
    assert user.is_staff is False


@pytest.mark.django_db
def test_already_superuser_unchanged():
    """Test that users who are already superusers remain unchanged"""
    # Create a user who is both staff and superuser
    user = User.objects.create_user(
        username="superuser",
        password="testpass123",
        is_staff=True,
        is_superuser=True
    )
    
    # Verify initial state
    assert user.is_staff is True
    assert user.is_superuser is True
    
    # Login the user
    client = Client()
    response = client.post(reverse("login"), {
        "username": "superuser",
        "password": "testpass123"
    })
    
    # Refresh user from database
    user.refresh_from_db()
    
    # Verify the user is still a superuser
    assert user.is_superuser is True
    assert user.is_staff is True
