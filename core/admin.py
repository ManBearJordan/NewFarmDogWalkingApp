from django.contrib import admin
from .models import StripeSettings, Client, Pet, Booking, BookingPet, AdminEvent, SubOccurrence


@admin.register(StripeSettings)
class StripeSettingsAdmin(admin.ModelAdmin):
    list_display = ['is_live_mode']
    fields = ['stripe_secret_key', 'is_live_mode']


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'status', 'credit_cents']
    list_filter = ['status']
    search_fields = ['name', 'email', 'phone']


@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'species', 'breed']
    list_filter = ['species']
    search_fields = ['name', 'client__name', 'breed']


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['service_name', 'client', 'start_dt', 'end_dt', 'status', 'price_cents', 'deleted']
    list_filter = ['status', 'deleted', 'service_code']
    search_fields = ['service_name', 'client__name', 'location']
    date_hierarchy = 'start_dt'


@admin.register(BookingPet)
class BookingPetAdmin(admin.ModelAdmin):
    list_display = ['booking', 'pet']
    list_filter = ['pet__species']
    search_fields = ['booking__service_name', 'pet__name']


@admin.register(AdminEvent)
class AdminEventAdmin(admin.ModelAdmin):
    list_display = ['title', 'due_dt']
    date_hierarchy = 'due_dt'
    search_fields = ['title', 'notes']


@admin.register(SubOccurrence)
class SubOccurrenceAdmin(admin.ModelAdmin):
    list_display = ['stripe_subscription_id', 'start_dt', 'end_dt', 'active']
    list_filter = ['active']
    search_fields = ['stripe_subscription_id']
    date_hierarchy = 'start_dt'