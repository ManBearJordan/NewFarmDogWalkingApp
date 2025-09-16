"""
URL routing for the core app REST API.

Defines the API endpoints for the dog walking application.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ClientViewSet, SubscriptionViewSet, BookingViewSet, ScheduleViewSet

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'clients', ClientViewSet)
router.register(r'subscriptions', SubscriptionViewSet)
router.register(r'bookings', BookingViewSet)
router.register(r'schedules', ScheduleViewSet)

app_name = 'core'

urlpatterns = [
    # Include the router URLs
    path('api/', include(router.urls)),
]