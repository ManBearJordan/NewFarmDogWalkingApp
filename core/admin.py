from django.contrib import admin
from .models import (
    StripeSettings, Client, Pet, Booking, BookingPet, AdminEvent, SubOccurrence, Tag,
    StripeKeyAudit, ServiceDefaults, TimetableBlock, BlockCapacity, CapacityHold
)


@admin.register(StripeKeyAudit)
class StripeKeyAuditAdmin(admin.ModelAdmin):
    list_display = ("when", "user", "previous_mode", "new_mode", "previous_test_or_live", "new_test_or_live")
    list_filter = ("previous_mode", "new_mode", "previous_test_or_live", "new_test_or_live")
    search_fields = ("user__username", "note")


@admin.register(StripeSettings)
class StripeSettingsAdmin(admin.ModelAdmin):
    list_display = ['is_live_mode']
    fields = ['stripe_secret_key', 'is_live_mode']


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'status', 'credit_cents', 'can_self_reschedule', 'user_link']
    list_filter = ['status', 'can_self_reschedule']
    search_fields = ['name', 'email', 'phone']
    actions = ['disable_portal_login', 'remove_portal_login']

    def user_link(self, obj):
        return obj.user.username if obj.user else "—"
    user_link.short_description = "Portal user"

    def disable_portal_login(self, request, queryset):
        for cl in queryset:
            if cl.user:
                cl.user.is_active = False
                cl.user.save()
        self.message_user(request, "Selected clients' logins disabled.")
    disable_portal_login.short_description = "Disable portal login"

    def remove_portal_login(self, request, queryset):
        for cl in queryset:
            if cl.user:
                u = cl.user
                cl.user = None
                cl.save()
                # If you prefer to fully delete the user, uncomment:
                # u.delete()
        self.message_user(request, "Selected clients' portal user unlinked.")
    remove_portal_login.short_description = "Remove portal login"


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


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "color", "created_at")
    search_fields = ("name",)


@admin.register(ServiceDefaults)
class ServiceDefaultsAdmin(admin.ModelAdmin):
    list_display = ("service_code", "duration_minutes", "notes")
    search_fields = ("service_code",)


@admin.register(TimetableBlock)
class TimetableBlockAdmin(admin.ModelAdmin):
    list_display = ("date", "start_time", "end_time", "label")
    list_filter = ("date",)
    date_hierarchy = "date"


@admin.register(BlockCapacity)
class BlockCapacityAdmin(admin.ModelAdmin):
    list_display = ("block", "service_code", "capacity", "allow_overlap")
    list_filter = ("service_code",)


@admin.register(CapacityHold)
class CapacityHoldAdmin(admin.ModelAdmin):
    list_display = ("token", "block", "service_code", "client", "expires_at")
    list_filter = ("service_code",)
    date_hierarchy = "expires_at"