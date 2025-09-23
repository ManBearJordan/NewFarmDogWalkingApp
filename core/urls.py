"""
URL configuration for the core app.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.client_list, name='home'),
    path('clients/', views.client_list, name='client_list'),
    path('clients/new/', views.client_create, name='client_create'),
    path('bookings/create-batch/', views.booking_create_batch, name='booking_create_batch'),
    # Bookings tab (list & manage)
    path("bookings/", views.booking_list, name="booking_list"),
    path("bookings/<int:booking_id>/open-invoice/", views.booking_open_invoice, name="booking_open_invoice"),
    path("bookings/<int:booking_id>/delete/", views.booking_soft_delete, name="booking_soft_delete"),
    path("bookings/export/ics/", views.booking_export_ics, name="booking_export_ics"),
    path('clients/<int:client_id>/credit/', views.client_add_credit, name='client_add_credit'),
    path('calendar/', views.calendar_view, name='calendar_view'),
    path('reports/invoices/', views.reports_invoices_list, name='reports_invoices_list'),
    # Subscriptions tab
    path("subscriptions/", views.subscriptions_list, name="subscriptions_list"),
    path("subscriptions/sync/", views.subscriptions_sync, name="subscriptions_sync"),
    path("subscriptions/<str:sub_id>/delete/", views.subscription_delete, name="subscription_delete"),
    # API: service info for price autofill
    path("api/service-info/", views.api_service_info, name="api_service_info"),
    # Pets
    path("pets/", views.PetListView.as_view(), name="pet_list"),
    path("pets/new/", views.PetCreateView.as_view(), name="pet_create"),
    path("pets/<int:pk>/edit/", views.PetUpdateView.as_view(), name="pet_edit"),
    path("pets/<int:pk>/delete/", views.PetDeleteView.as_view(), name="pet_delete"),
    # Admin Status (Stripe management)
    path("admin/stripe/", views.stripe_status_view, name="stripe_status"),
    path("admin/stripe/diagnostics/", views.stripe_diagnostics_view, name="stripe_diagnostics"),
    # Admin Tasks (AdminEvent CRUD)
    path("admin/tasks/", views.admin_tasks_list, name="admin_tasks_list"),
    path("admin/tasks/new/", views.admin_task_create, name="admin_task_create"),
    path("admin/tasks/<int:pk>/edit/", views.admin_task_edit, name="admin_task_edit"),
    path("admin/tasks/<int:pk>/delete/", views.admin_task_delete, name="admin_task_delete"),
    # CRM Tags
    path("crm/tags/", views.tags_list, name="tags_list"),
    path("crm/tags/new/", views.tag_create, name="tag_create"),
    path("crm/tags/<int:pk>/edit/", views.tag_edit, name="tag_edit"),
    path("crm/tags/<int:pk>/delete/", views.tag_delete, name="tag_delete"),
]