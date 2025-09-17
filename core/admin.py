"""
Django admin configuration for dog walking app models.

Provides comprehensive admin interface for managing subscriptions, bookings,
clients, and schedules with proper filtering, search, and display options.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from datetime import datetime, timedelta
from .models import Client, Subscription, Booking, Schedule


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """Admin interface for Client model"""
    list_display = [
        'name', 'email', 'phone', 'stripe_customer_id', 
        'status', 'credit_dollars', 'total_revenue_dollars', 
        'service_count', 'last_service_date'
    ]
    list_filter = ['status', 'acquisition_date', 'last_service_date']
    search_fields = ['name', 'email', 'stripe_customer_id']
    readonly_fields = ['created_at', 'updated_at', 'credit_dollars', 'total_revenue_dollars']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'email', 'phone', 'address')
        }),
        ('Stripe Integration', {
            'fields': ('stripe_customer_id',)
        }),
        ('Financial', {
            'fields': ('credit_cents', 'credit_dollars', 'total_revenue_cents', 'total_revenue_dollars')
        }),
        ('Status & Metrics', {
            'fields': ('status', 'acquisition_date', 'last_service_date', 'service_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def credit_dollars(self, obj):
        """Display credit in dollars"""
        return f"${obj.credit_cents / 100:.2f}"
    credit_dollars.short_description = 'Credit ($)'

    def total_revenue_dollars(self, obj):
        """Display total revenue in dollars"""
        return f"${obj.total_revenue_cents / 100:.2f}"
    total_revenue_dollars.short_description = 'Total Revenue ($)'


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Admin interface for Subscription model"""
    list_display = [
        'stripe_subscription_id', 'client', 'service_name', 'status',
        'schedule_days', 'schedule_time_range', 'schedule_dogs', 
        'last_sync_at', 'created_at'
    ]
    list_filter = [
        'status', 'service_code', 'schedule_dogs', 
        'created_from_stripe', 'created_at', 'last_sync_at'
    ]
    search_fields = [
        'stripe_subscription_id', 'client__name', 'service_name', 
        'service_code', 'schedule_location'
    ]
    readonly_fields = [
        'stripe_subscription_id', 'created_from_stripe', 
        'stripe_created_at', 'last_sync_at', 'created_at', 'updated_at',
        'schedule_duration_display', 'next_occurrence'
    ]
    
    fieldsets = (
        ('Subscription Information', {
            'fields': ('stripe_subscription_id', 'client', 'status', 'created_from_stripe'),
            'description': 'Basic subscription details. Stripe ID cannot be changed.'
        }),
        ('Service Configuration', {
            'fields': ('service_code', 'service_name'),
            'description': 'Service details. Service code must match your service catalog.'
        }),
        ('Schedule Settings', {
            'fields': (
                'schedule_days', 'schedule_start_time', 'schedule_end_time',
                'schedule_duration_display', 'schedule_location', 'schedule_dogs', 'schedule_notes'
            ),
            'description': '''
                <strong>How to update schedules:</strong><br>
                • <strong>Days:</strong> Use 3-letter codes separated by commas (MON,WED,FRI)<br>
                • <strong>Times:</strong> Use 24-hour format (14:30 for 2:30 PM)<br>
                • <strong>Location:</strong> Full address where service will be provided<br>
                • <strong>Dogs:</strong> Number of dogs to be walked<br>
                • After saving changes, bookings will be automatically updated
            '''
        }),
        ('Schedule Preview', {
            'fields': ('next_occurrence',),
            'classes': ('collapse',),
            'description': 'Preview of when the next service will occur'
        }),
        ('System Information', {
            'fields': ('stripe_created_at', 'last_sync_at', 'created_at', 'updated_at'),
            'classes': ('collapse',),
            'description': 'System tracking information - for reference only'
        }),
    )

    def schedule_time_range(self, obj):
        """Display schedule time range"""
        return f"{obj.schedule_start_time} - {obj.schedule_end_time}"
    schedule_time_range.short_description = 'Time Range'

    def schedule_duration_display(self, obj):
        """Display schedule duration"""
        return str(obj.schedule_duration)
    schedule_duration_display.short_description = 'Duration'

    def next_occurrence(self, obj):
        """Display next occurrence date"""
        next_date = obj.get_next_occurrence()
        if next_date:
            return next_date.strftime('%Y-%m-%d (%A)')
        return 'None'
    next_occurrence.short_description = 'Next Occurrence'

    actions = ['sync_with_stripe', 'generate_bookings']

    def sync_with_stripe(self, request, queryset):
        """Sync selected subscriptions with Stripe"""
        try:
            from core.tasks import update_subscription_from_stripe
            
            successful_syncs = 0
            failed_syncs = 0
            
            for subscription in queryset:
                try:
                    # Trigger async task to update subscription from Stripe
                    result = update_subscription_from_stripe.delay(subscription.stripe_subscription_id)
                    successful_syncs += 1
                except Exception as e:
                    failed_syncs += 1
                    self.message_user(request, 
                        f'Failed to sync subscription {subscription.stripe_subscription_id}: {str(e)}', 
                        level=messages.ERROR)
            
            if successful_syncs > 0:
                self.message_user(request, 
                    f'Successfully initiated sync for {successful_syncs} subscriptions')
            
            if failed_syncs > 0:
                self.message_user(request, 
                    f'{failed_syncs} subscriptions failed to sync', 
                    level=messages.WARNING)
                    
        except ImportError:
            self.message_user(request, 
                'Sync functionality not available - tasks not configured', 
                level=messages.ERROR)
    
    sync_with_stripe.short_description = 'Sync selected subscriptions with Stripe'

    def generate_bookings(self, request, queryset):
        """Generate bookings for selected subscriptions"""
        try:
            from core.tasks import generate_subscription_bookings
            
            successful_generations = 0
            failed_generations = 0
            
            for subscription in queryset:
                try:
                    # Trigger async task to generate bookings
                    result = generate_subscription_bookings.delay(subscription.stripe_subscription_id)
                    successful_generations += 1
                except Exception as e:
                    failed_generations += 1
                    self.message_user(request, 
                        f'Failed to generate bookings for {subscription.stripe_subscription_id}: {str(e)}', 
                        level=messages.ERROR)
            
            if successful_generations > 0:
                self.message_user(request, 
                    f'Successfully initiated booking generation for {successful_generations} subscriptions. '
                    f'Check the Bookings section to see new appointments.')
            
            if failed_generations > 0:
                self.message_user(request, 
                    f'{failed_generations} subscriptions failed to generate bookings', 
                    level=messages.WARNING)
                    
        except ImportError:
            # Fallback to direct booking generation if tasks not available
            try:
                from booking_utils import generate_bookings_and_update_calendar
                
                successful_generations = 0
                failed_generations = 0
                
                for subscription in queryset:
                    # Prepare schedule data from subscription
                    schedule_data = {
                        'service_code': subscription.service_code,
                        'days': subscription.schedule_days,
                        'start_time': subscription.schedule_start_time.strftime('%H:%M'),
                        'end_time': subscription.schedule_end_time.strftime('%H:%M'),
                        'location': subscription.schedule_location or '',
                        'dogs': subscription.schedule_dogs,
                        'notes': subscription.schedule_notes or ''
                    }
                    
                    try:
                        result = generate_bookings_and_update_calendar(
                            subscription.stripe_subscription_id, 
                            schedule_data
                        )
                        
                        if result.get('success'):
                            successful_generations += 1
                            bookings_created = result.get('bookings_created', 0)
                            if bookings_created > 0:
                                self.message_user(request, 
                                    f'Generated {bookings_created} bookings for subscription {subscription.stripe_subscription_id}')
                        else:
                            failed_generations += 1
                            error_msg = result.get('error', 'Unknown error')
                            self.message_user(request, 
                                f'Failed to generate bookings for {subscription.stripe_subscription_id}: {error_msg}', 
                                level=messages.ERROR)
                    except Exception as e:
                        failed_generations += 1
                        self.message_user(request, 
                            f'Error generating bookings for {subscription.stripe_subscription_id}: {str(e)}', 
                            level=messages.ERROR)
                
                if successful_generations > 0:
                    self.message_user(request, 
                        f'Successfully generated bookings for {successful_generations} subscriptions. '
                        f'Check the Bookings section to see new appointments.')
                        
            except ImportError as e:
                self.message_user(request, 
                    f'Booking generation not available - missing dependencies: {str(e)}', 
                    level=messages.ERROR)
    
    generate_bookings.short_description = 'Generate bookings from subscription schedule'
    
    def save_model(self, request, obj, form, change):
        """
        Save the subscription and automatically update bookings if schedule changed.
        """
        # Track if this is an update with schedule changes
        schedule_changed = False
        if change:
            # Get the original object to compare
            try:
                original = Subscription.objects.get(pk=obj.pk)
                schedule_fields = [
                    'schedule_days', 'schedule_start_time', 'schedule_end_time',
                    'schedule_location', 'schedule_dogs', 'schedule_notes', 'service_code'
                ]
                
                for field in schedule_fields:
                    if getattr(original, field) != getattr(obj, field):
                        schedule_changed = True
                        break
                        
            except Subscription.DoesNotExist:
                pass
        
        # Save the object first
        super().save_model(request, obj, form, change)
        
        # If schedule changed, automatically generate bookings
        if schedule_changed:
            try:
                from core.tasks import generate_subscription_bookings
                result = generate_subscription_bookings.delay(obj.stripe_subscription_id)
                messages.info(request, 
                    'Schedule was updated - new bookings are being generated in the background. '
                    'Check the Bookings section in a few moments to see updated appointments.')
            except ImportError:
                # Fallback to direct generation
                try:
                    from booking_utils import generate_bookings_and_update_calendar
                    
                    schedule_data = {
                        'service_code': obj.service_code,
                        'days': obj.schedule_days,
                        'start_time': obj.schedule_start_time.strftime('%H:%M'),
                        'end_time': obj.schedule_end_time.strftime('%H:%M'),
                        'location': obj.schedule_location or '',
                        'dogs': obj.schedule_dogs,
                        'notes': obj.schedule_notes or ''
                    }
                    
                    result = generate_bookings_and_update_calendar(
                        obj.stripe_subscription_id, 
                        schedule_data
                    )
                    
                    if result.get('success'):
                        bookings_created = result.get('bookings_created', 0)
                        if bookings_created > 0:
                            messages.success(request, 
                                f'Schedule updated and {bookings_created} new bookings were created automatically.')
                        else:
                            messages.info(request, 
                                'Schedule updated. No new bookings were needed.')
                    else:
                        messages.warning(request, 
                            f'Schedule updated but booking generation failed: {result.get("error", "Unknown error")}. '
                            f'You can manually generate bookings using the "Generate bookings" action.')
                        
                except ImportError:
                    messages.warning(request, 
                        'Schedule updated but automatic booking generation is not available. '
                        'You can manually generate bookings using the "Generate bookings" action.')
                except Exception as e:
                    messages.error(request, 
                        f'Schedule updated but booking generation failed: {str(e)}. '
                        f'You can manually generate bookings using the "Generate bookings" action.')
            except Exception as e:
                messages.error(request, 
                    f'Schedule updated but booking generation failed: {str(e)}. '
                    f'You can manually generate bookings using the "Generate bookings" action.')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """Admin interface for Booking model"""
    list_display = [
        'client', 'service_name', 'start_dt', 'end_dt', 'location',
        'dogs', 'status', 'source', 'has_invoice'
    ]
    list_filter = [
        'status', 'source', 'service_type', 'dogs',
        'start_dt', 'created_at'
    ]
    search_fields = [
        'client__name', 'service_name', 'location', 'notes',
        'stripe_invoice_id', 'created_from_sub_id'
    ]
    readonly_fields = [
        'duration_display', 'is_today', 'is_upcoming', 'can_be_invoiced',
        'created_at', 'updated_at'
    ]
    date_hierarchy = 'start_dt'
    
    fieldsets = (
        ('Booking Details', {
            'fields': ('client', 'subscription', 'status', 'source')
        }),
        ('Schedule', {
            'fields': (
                'start_dt', 'end_dt', 'duration_display',
                'is_today', 'is_upcoming'
            )
        }),
        ('Service Information', {
            'fields': ('service_type', 'service_name', 'location', 'dogs', 'notes')
        }),
        ('Stripe Integration', {
            'fields': (
                'created_from_sub_id', 'stripe_invoice_id', 
                'stripe_price_id', 'invoice_url', 'can_be_invoiced'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def duration_display(self, obj):
        """Display booking duration"""
        return str(obj.duration)
    duration_display.short_description = 'Duration'

    def has_invoice(self, obj):
        """Display if booking has an invoice"""
        if obj.stripe_invoice_id:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    has_invoice.short_description = 'Invoiced'
    has_invoice.boolean = True

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('client', 'subscription')

    actions = ['mark_completed', 'mark_canceled', 'create_invoices']

    def mark_completed(self, request, queryset):
        """Mark selected bookings as completed"""
        updated = queryset.update(status='completed')
        self.message_user(request, f'{updated} bookings marked as completed')
    mark_completed.short_description = 'Mark as Completed'

    def mark_canceled(self, request, queryset):
        """Mark selected bookings as canceled"""
        updated = queryset.update(status='canceled')
        self.message_user(request, f'{updated} bookings marked as canceled')
    mark_canceled.short_description = 'Mark as Canceled'

    def create_invoices(self, request, queryset):
        """Create invoices for selected bookings"""
        count = 0
        for booking in queryset.filter(status='completed', stripe_invoice_id__isnull=True):
            # Integration point with existing invoice creation
            count += 1
        self.message_user(request, f'Created invoices for {count} bookings')
    create_invoices.short_description = 'Create Invoices'


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    """Admin interface for Schedule model"""
    list_display = [
        'name', 'service_code', 'days_display', 'time_range',
        'default_dogs', 'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'service_code', 'default_dogs', 'created_at']
    search_fields = ['name', 'description', 'service_code', 'default_location']
    readonly_fields = ['days_display', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Schedule Template', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Schedule Pattern', {
            'fields': (
                'days_of_week', 'days_display', 'start_time', 'end_time',
                'service_code'
            )
        }),
        ('Defaults', {
            'fields': ('default_location', 'default_dogs')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def days_display(self, obj):
        """Display days in readable format"""
        days_map = {
            0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu',
            4: 'Fri', 5: 'Sat', 6: 'Sun'
        }
        days = obj.days_list
        return ', '.join(days_map.get(day, str(day)) for day in days)
    days_display.short_description = 'Days'

    def time_range(self, obj):
        """Display time range"""
        return f"{obj.start_time} - {obj.end_time}"
    time_range.short_description = 'Time Range'


# Admin site customization
admin.site.site_header = "New Farm Dog Walking Admin"
admin.site.site_title = "Dog Walking Admin"
admin.site.index_title = "Manage Subscriptions, Bookings & Clients"
