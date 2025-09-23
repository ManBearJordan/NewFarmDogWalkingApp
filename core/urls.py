"""
URL configuration for the core app.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('clients/', views.client_list, name='client_list'),
    path('bookings/create-batch/', views.booking_create_batch, name='booking_create_batch'),
    path('clients/<int:client_id>/credit/', views.client_add_credit, name='client_add_credit'),
    path('calendar/', views.calendar_view, name='calendar_view'),
    path('reports/invoices/', views.reports_invoices_list, name='reports_invoices_list'),
    # Pets
    path("pets/", views.PetListView.as_view(), name="pet_list"),
    path("pets/new/", views.PetCreateView.as_view(), name="pet_create"),
    path("pets/<int:pk>/edit/", views.PetUpdateView.as_view(), name="pet_edit"),
    path("pets/<int:pk>/delete/", views.PetDeleteView.as_view(), name="pet_delete"),
]