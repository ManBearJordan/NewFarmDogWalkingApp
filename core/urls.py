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
    path('bookings/export/all.ics', views.bookings_export_all_ics, name='bookings_export_all_ics'),
    path('bookings/export/', views.bookings_export_by_ids_ics, name='bookings_export_by_ids_ics'),
]