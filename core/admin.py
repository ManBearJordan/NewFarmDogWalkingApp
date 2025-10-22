from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    StripeSettings, Client, Pet, Booking, BookingPet, AdminEvent, AdminTask, SubOccurrence, Tag,
    StripeKeyAudit, Service, ServiceDefaults, TimetableBlock, BlockCapacity, CapacityHold,
    StripeSubscriptionLink, StripeSubscriptionSchedule, StripePriceMap
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
    list_display = ['service_name', 'client', 'start_dt', 'end_dt', 'status', 'price_cents', 'deleted', 'review_flag', 'review_summary', 'invoice_meta_link']
    list_filter = ['status', 'deleted', 'service_code', 'requires_admin_review']
    search_fields = ['service_name', 'client__name', 'location']
    date_hierarchy = 'start_dt'

    def review_flag(self, obj):
        return "⚠️" if getattr(obj, "requires_admin_review", False) else "—"
    review_flag.short_description = "Review"

    def review_summary(self, obj):
        rd = getattr(obj, "review_diff", None)
        if not rd:
            return "—"
        # show changed keys only
        try:
            keys = ", ".join(sorted(rd.keys()))
            return keys or "—"
        except Exception:
            return "(diff)"
    review_summary.short_description = "Diff"

    def invoice_meta_link(self, obj):
        if not obj.stripe_invoice_id:
            return "—"
        url = reverse("admin_invoice_metadata", args=[obj.id])
        return format_html('<a href="{}">Invoice metadata</a>', url)
    invoice_meta_link.short_description = "Inspect"


@admin.register(BookingPet)
class BookingPetAdmin(admin.ModelAdmin):
    list_display = ['booking', 'pet']
    list_filter = ['pet__species']
    search_fields = ['booking__service_name', 'pet__name']


@admin.register(AdminTask)
class AdminTaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'due_dt']
    date_hierarchy = 'due_dt'
    search_fields = ['title', 'notes']


@admin.register(AdminEvent)
class AdminEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_type", "actor", "booking", "short_message")
    list_filter = ("event_type",)
    search_fields = ("message", "context")
    ordering = ("-created_at", "-id")
    readonly_fields = ("created_at", "event_type", "message", "actor", "booking", "context")

    def short_message(self, obj):
        msg = (obj.message or "").strip()
        return (msg[:80] + "…") if len(msg) > 80 else msg
    short_message.short_description = "Message"

    def has_add_permission(self, request):
        # Audit events are write-once via code, not manually created
        return False

    def has_delete_permission(self, request, obj=None):
        # Preserve audit trail
        return False


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


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "duration_minutes", "is_active")
    list_filter = ("is_active",)


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


@admin.register(StripeSubscriptionLink)
class StripeSubscriptionLinkAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "stripe_subscription_id", "service_code", "active")
    list_filter = ("active",)
    search_fields = ("stripe_subscription_id", "client__name", "service_code")


@admin.register(StripeSubscriptionSchedule)
class StripeSubscriptionScheduleAdmin(admin.ModelAdmin):
    list_display = ("id", "get_client", "get_stripe_subscription_id", "get_service_code", "repeats", "days", "start_time", "location", "get_active")
    list_filter = ("repeats",)
    search_fields = ("sub__stripe_subscription_id", "sub__client__name", "sub__service_code", "days", "location")
    
    def get_client(self, obj):
        return obj.sub.client if obj.sub else "—"
    get_client.short_description = "Client"
    
    def get_stripe_subscription_id(self, obj):
        return obj.sub.stripe_subscription_id if obj.sub else "—"
    get_stripe_subscription_id.short_description = "Stripe Sub ID"
    
    def get_service_code(self, obj):
        return obj.sub.service_code if obj.sub else "—"
    get_service_code.short_description = "Service Code"
    
    def get_active(self, obj):
        return obj.sub.active if obj.sub else False
    get_active.short_description = "Active"
    get_active.boolean = True


@admin.register(StripePriceMap)
class StripePriceMapAdmin(admin.ModelAdmin):
    list_display = ("price_id", "product_id", "nickname", "service", "active", "updated_at")
    list_filter = ("active",)
    search_fields = ("price_id", "product_id", "nickname", "service__code", "service__name")
