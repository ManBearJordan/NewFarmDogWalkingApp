"""
URL configuration for the core app.
"""

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views, views_admin_capacity, views_portal, views_admin_subs, views_webhooks, views_settings, views_misc, views_client, admin_tools

urlpatterns = [
    path("", views_portal.root_router, name="root"),
    path("portal/", views_client.client_dashboard, name="portal_home"),
    path("admin-tools/reconcile/", admin_tools.reconcile_list, name="admin_reconcile"),
    path("admin-tools/reconcile/mark-paid/<int:booking_id>/", admin_tools.reconcile_mark_paid, name="admin_reconcile_paid"),
    path("calendar/", views_client.client_calendar, name="calendar"),
    path("portal/book/", views_client.booking_create, name="portal_booking_create"),
    path("portal/confirm/", views_client.booking_confirm, name="portal_booking_confirm"),
    path("healthz/", views_misc.health_check, name="healthz"),
    path('clients/', views.client_list, name='client_list'),
    path('clients/new/', views.client_create, name='client_create'),
    # Clients: Stripe + Credit actions
    path("clients/stripe/sync/", views.clients_stripe_sync, name="clients_stripe_sync"),
    path("clients/<int:client_id>/stripe/link/", views.client_stripe_link, name="client_stripe_link"),
    path("clients/<int:client_id>/stripe/open/", views.client_stripe_open, name="client_stripe_open"),
    path("clients/<int:client_id>/credit/add/", views.client_credit_add, name="client_credit_add"),
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
    # --- Admin: Stripe Key update ---
    path("admin/stripe/status/", views.stripe_status_view, name="stripe_status"),
    path("admin/stripe/key/update/", views.stripe_key_update, name="stripe_key_update"),
    # --- Auth (client portal) ---
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    # --- Portal (original booking flow with credit/invoice support) ---
    path("portal/bookings/new/", views.portal_booking_create, name="portal_booking_create_old"),
    path("portal/bookings/confirm/", views.portal_booking_confirm, name="portal_booking_confirm_old"),
    # Portal (pre-pay flow with flexible capacity)
    path("portal/bookings/new-prepay/", views_portal.portal_booking_new, name="portal_booking_new_prepay"),
    path("portal/blocks/", views_portal.portal_blocks_for_date, name="portal_blocks_for_date"),
    path("portal/checkout/start/", views_portal.portal_checkout_start, name="portal_checkout_start"),
    path("portal/checkout/finalize/", views_portal.portal_checkout_finalize, name="portal_checkout_finalize"),
    # --- Calendar: troubleshoot sync ---
    path("calendar/troubleshoot-sync/", views.calendar_troubleshoot_sync, name="calendar_troubleshoot_sync"),
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
    # Admin capacity editor
    path("admin/capacity/", views_admin_capacity.capacity_edit, name="admin_capacity_edit"),
    # Admin subscriptions dashboard
    path("admin/subs/", views_admin_subs.subs_dashboard, name="admin_subs_dashboard"),
    path("admin/subs/<str:sub_id>/schedule/", views_admin_subs.subs_set_schedule, name="admin_subs_set_schedule"),
    path("admin/subs/occ/<int:occ_id>/finalize/", views_admin_subs.subs_finalize_occurrence, name="admin_subs_finalize_occurrence"),
    # Stripe webhook
    path("stripe/webhooks/", views_webhooks.stripe_webhook, name="stripe_webhook"),
    # Service settings
    path('settings/services/', views_settings.service_settings, name='service_settings'),
]