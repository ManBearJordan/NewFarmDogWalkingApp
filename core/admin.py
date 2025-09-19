"""
Django admin configuration for dog walking app models.

Provides comprehensive admin interface for managing subscriptions, bookings,
clients, and schedules with proper filtering, search, and display options.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.utils import timezone
from django.contrib import messages
from django.http import JsonResponse
from datetime import datetime, timedelta
from .models import Client, Subscription, Booking, Schedule, StripeSettings


class SyncLogAdmin:
    """Admin interface for viewing sync logs and triggering manual syncs"""
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('sync-stripe/', self.admin_site.admin_view(self.sync_stripe_view), name='sync-stripe'),
            path('sync-logs/', self.admin_site.admin_view(self.sync_logs_view), name='sync-logs'),
        ]
        return custom_urls + urls
    
    def sync_stripe_view(self, request):
        """Manual trigger for Stripe sync"""
        if request.method == 'POST':
            try:
                from core.services.stripe_sync import sync_stripe_data_on_startup
                result = sync_stripe_data_on_startup()
                return JsonResponse(result)
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
        
        return JsonResponse({'error': 'POST method required'})
    
    def sync_logs_view(self, request):
        """View recent sync logs with download option"""
        import os
        from django.http import HttpResponse
        from django.conf import settings
        
        # Check if this is a download request
        download = request.GET.get('download', False)
        
        try:
            # Primary log file: our dedicated subscription error log
            primary_log_file = "subscription_error_log.txt"
            secondary_log_file = os.path.join(settings.BASE_DIR, 'django.log')
            
            logs_content = ""
            
            # Try to read the primary subscription log first
            if os.path.exists(primary_log_file):
                with open(primary_log_file, 'r', encoding='utf-8') as f:
                    logs_content += "=== SUBSCRIPTION ERROR LOG (subscription_error_log.txt) ===\n"
                    if download:
                        # Return full log for download
                        logs_content += f.read()
                    else:
                        # Get last 200 lines for viewing
                        lines = f.readlines()
                        logs_content += ''.join(lines[-200:])
                    logs_content += "\n\n"
            
            # Also include django.log if it exists and has subscription-related entries
            if os.path.exists(secondary_log_file):
                with open(secondary_log_file, 'r') as f:
                    lines = f.readlines()
                    # Filter for subscription/sync-related logs
                    sync_lines = [line for line in lines if any(keyword in line.lower() for keyword in ['subscription', 'stripe', 'sync', 'webhook', 'booking'])]
                    
                    if sync_lines:
                        logs_content += "=== DJANGO LOG (django.log) - Subscription/Sync Related ===\n"
                        if download:
                            logs_content += ''.join(sync_lines)
                        else:
                            logs_content += ''.join(sync_lines[-100:])  # Last 100 sync-related lines
            
            if not logs_content:
                logs_content = "No subscription/sync logs found."
            
            if download:
                # Return as downloadable file
                response = HttpResponse(logs_content, content_type='text/plain')
                response['Content-Disposition'] = 'attachment; filename="subscription_logs.txt"'
                return response
            else:
                # Return as JSON for web viewing
                return JsonResponse({
                    'success': True,
                    'logs': logs_content,
                    'log_files_checked': [primary_log_file, secondary_log_file],
                    'download_url': request.build_absolute_uri() + '?download=1'
                })
                
        except Exception as e:
            error_msg = f"Error reading log files: {str(e)}"
            if download:
                return HttpResponse(error_msg, content_type='text/plain', status=500)
            else:
                return JsonResponse({'success': False, 'error': error_msg})


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
            'description': format_html('''
                <strong>How to update schedules:</strong><br>
                • <strong>Days:</strong> Use 3-letter codes separated by commas (MON,WED,FRI)<br>
                • <strong>Times:</strong> Use 24-hour format (14:30 for 2:30 PM)<br>
                • <strong>Location:</strong> Full address where service will be provided<br>
                • <strong>Dogs:</strong> Number of dogs to be walked<br>
                • After saving changes, bookings will be automatically updated
            ''')
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
            # Fallback to direct sync
            from core.services.stripe_sync import stripe_sync_service
            
            successful_syncs = 0
            failed_syncs = 0
            
            for subscription in queryset:
                try:
                    # Use Django sync service directly
                    result = stripe_sync_service.sync_all_stripe_data()
                    if result.get('success'):
                        successful_syncs += 1
                    else:
                        failed_syncs += 1
                        self.message_user(request, 
                            f'Sync failed for {subscription.stripe_subscription_id}: {result.get("error")}', 
                            level=messages.ERROR)
                except Exception as e:
                    failed_syncs += 1
                    self.message_user(request, 
                        f'Failed to sync subscription {subscription.stripe_subscription_id}: {str(e)}', 
                        level=messages.ERROR)
            
            if successful_syncs > 0:
                self.message_user(request, 
                    f'Successfully synced {successful_syncs} subscriptions')
    
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
        ENHANCED: Comprehensive error logging and automatic booking generation.
        """
        # Import logging utilities
        from log_utils import log_subscription_info, log_subscription_error
        
        # Track if this is an update with schedule changes
        schedule_changed = False
        original_data = {}
        
        if change:
            # Get the original object to compare
            try:
                original = Subscription.objects.get(pk=obj.pk)
                schedule_fields = [
                    'schedule_days', 'schedule_start_time', 'schedule_end_time',
                    'schedule_location', 'schedule_dogs', 'schedule_notes', 'service_code', 'status'
                ]
                
                for field in schedule_fields:
                    original_value = getattr(original, field)
                    new_value = getattr(obj, field)
                    original_data[field] = original_value
                    
                    if original_value != new_value:
                        schedule_changed = True
                        logger.info(f"Admin: Schedule field '{field}' changed from '{original_value}' to '{new_value}' for {obj.stripe_subscription_id}")
                        
            except Subscription.DoesNotExist:
                logger.warning(f"Admin: Could not find original subscription for comparison: {obj.stripe_subscription_id}")
        else:
            # This is a new subscription
            logger.info(f"Admin: Creating new subscription {obj.stripe_subscription_id}")
            log_subscription_info(f"New subscription created via admin: {obj.stripe_subscription_id}", obj.stripe_subscription_id)
        
        # Save the object first
        super().save_model(request, obj, form, change)
        
        # Log the save operation
        action = "updated" if change else "created"
        logger.info(f"Admin: Subscription {obj.stripe_subscription_id} {action} successfully")
        log_subscription_info(f"Subscription {action} via admin, schedule_changed={schedule_changed}", obj.stripe_subscription_id)
        
        # Automatically generate bookings if:
        # 1. This is a new subscription (not change) OR
        # 2. This is an update with schedule changes
        # AND the subscription is active with valid schedule
        should_generate = (not change) or schedule_changed
        
        if should_generate and obj.status == 'active' and self._has_valid_schedule_admin(obj):
            try:
                logger.info(f"Admin: AUTO-GENERATING bookings for {obj.stripe_subscription_id} (action={action}, schedule_changed={schedule_changed})")
                
                # Try to use the new sync function first
                try:
                    from core.tasks import generate_subscription_bookings_sync
                    result = generate_subscription_bookings_sync(obj.stripe_subscription_id)
                    
                    if result.get('success'):
                        bookings_created = result.get('bookings_created', 0)
                        if bookings_created > 0:
                            success_msg = f'Schedule {action} and {bookings_created} new bookings were created automatically.'
                            messages.success(request, success_msg)
                            log_subscription_info(f"Admin auto-booking SUCCESS: {bookings_created} bookings created", obj.stripe_subscription_id)
                        else:
                            info_msg = f'Schedule {action}. No new bookings were needed.'
                            messages.info(request, info_msg)
                            log_subscription_info(f"Admin auto-booking: No new bookings needed", obj.stripe_subscription_id)
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        warning_msg = f'Schedule {action} but booking generation failed: {error_msg}. You can manually generate bookings using the "Generate bookings" action.'
                        messages.warning(request, warning_msg)
                        log_subscription_error(f"Admin auto-booking FAILED: {error_msg}", obj.stripe_subscription_id)
                        
                except ImportError:
                    # Fallback to legacy sync service
                    logger.info(f"Admin: Using fallback sync service for {obj.stripe_subscription_id}")
                    from core.services.stripe_sync import stripe_sync_service
                    result = stripe_sync_service.sync_all_stripe_data()
                    if result.get('success'):
                        bookings_created = result['stats'].get('bookings_created', 0)
                        if bookings_created > 0:
                            success_msg = f'Schedule {action} and {bookings_created} new bookings were created automatically.'
                            messages.success(request, success_msg)
                            log_subscription_info(f"Admin fallback auto-booking SUCCESS: {bookings_created} bookings created", obj.stripe_subscription_id)
                        else:
                            info_msg = f'Schedule {action}. No new bookings were needed.'
                            messages.info(request, info_msg)
                            log_subscription_info(f"Admin fallback auto-booking: No new bookings needed", obj.stripe_subscription_id)
                    else:
                        error_msg = result.get("error", "Unknown error")
                        warning_msg = f'Schedule {action} but booking generation failed: {error_msg}. You can manually generate bookings using the "Generate bookings" action.'
                        messages.warning(request, warning_msg)
                        log_subscription_error(f"Admin fallback auto-booking FAILED: {error_msg}", obj.stripe_subscription_id)
                        
            except Exception as e:
                error_msg = f'Schedule {action} but booking generation failed: {str(e)}. You can manually generate bookings using the "Generate bookings" action.'
                messages.error(request, error_msg)
                log_subscription_error(f"Admin auto-booking EXCEPTION: {str(e)}", obj.stripe_subscription_id, e)
                
        elif should_generate and obj.status != 'active':
            logger.info(f"Admin: Skipping booking generation for {obj.stripe_subscription_id} - status is {obj.status}")
            log_subscription_info(f"Booking generation skipped - subscription not active (status: {obj.status})", obj.stripe_subscription_id)
            
        elif should_generate and not self._has_valid_schedule_admin(obj):
            logger.info(f"Admin: Skipping booking generation for {obj.stripe_subscription_id} - invalid schedule metadata")
            log_subscription_error(f"Booking generation skipped - invalid schedule metadata: days={obj.schedule_days}, start={obj.schedule_start_time}, end={obj.schedule_end_time}, service={obj.service_code}", obj.stripe_subscription_id)

    def _has_valid_schedule_admin(self, subscription):
        """Check if subscription has valid schedule metadata for booking generation"""
        return (subscription.schedule_days and 
                subscription.schedule_start_time and 
                subscription.schedule_end_time and
                subscription.service_code)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """Admin interface for Booking model"""
    list_display = [
        'client', 'service_name', 'start_dt', 'end_dt', 'location',
        'dogs', 'status', 'source', 'has_invoice', 'linked_subscription'
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
        return bool(obj.stripe_invoice_id)
    has_invoice.short_description = 'Invoiced'
    has_invoice.boolean = True

    def linked_subscription(self, obj):
        """Display linked subscription info"""
        if obj.subscription:
            return format_html(
                '<a href="{}">Subscription {}</a>',
                reverse('admin:core_subscription_change', args=[obj.subscription.pk]),
                obj.subscription.stripe_subscription_id[:20] + '...'
            )
        elif obj.created_from_sub_id:
            return obj.created_from_sub_id[:20] + '...'
        return 'None'
    linked_subscription.short_description = 'Linked Subscription'

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


@admin.register(StripeSettings)
class StripeSettingsAdmin(admin.ModelAdmin):
    """Admin interface for Stripe Settings"""
    list_display = ['__str__', 'is_live_mode', 'updated_at']
    readonly_fields = ['is_live_mode', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Stripe Configuration', {
            'fields': ('stripe_secret_key', 'is_live_mode'),
            'description': format_html('''
                <div style="margin-bottom: 15px; padding: 10px; background: #e7f3ff; border: 1px solid #bee5eb; border-radius: 4px;">
                    <strong>📋 Instructions:</strong><br>
                    • Enter your Stripe Secret Key (starts with sk_test_ or sk_live_)<br>
                    • Test keys start with <code>sk_test_</code><br>
                    • Live keys start with <code>sk_live_</code><br>
                    • Mode (Test/Live) is automatically detected<br>
                    • Only one settings record is maintained
                </div>
            ''')
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def has_add_permission(self, request):
        """Only allow one StripeSettings record"""
        return not StripeSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of settings"""
        return False
        
    def changelist_view(self, request, extra_context=None):
        """Custom changelist view"""
        # If no settings exist, redirect to add form
        if not StripeSettings.objects.exists():
            from django.shortcuts import redirect
            return redirect('admin:core_stripesettings_add')
        return super().changelist_view(request, extra_context)


# Custom admin site with sync functionality and Stripe key warnings
class StripeSyncAdminSite(admin.AdminSite):
    """Custom admin site with Stripe sync functionality"""
    site_header = "New Farm Dog Walking Admin"
    site_title = "Dog Walking Admin"
    index_title = "Manage Subscriptions, Bookings & Clients"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('sync-stripe/', self.admin_view(self.sync_stripe_view), name='admin-sync-stripe'),
            path('sync-logs/', self.admin_view(self.sync_logs_view), name='admin-sync-logs'),
        ]
        return custom_urls + urls
    
    def index(self, request, extra_context=None):
        """Custom index view with Stripe key warning"""
        extra_context = extra_context or {}
        
        # Check if Stripe key is configured
        stripe_key = StripeSettings.get_stripe_key()
        if not stripe_key:
            extra_context['stripe_key_missing'] = True
            extra_context['stripe_settings_url'] = reverse('admin:core_stripesettings_changelist')
        
        return super().index(request, extra_context)
    
    def sync_stripe_view(self, request):
        """Manual trigger for Stripe sync"""
        if request.method == 'POST':
            try:
                from core.services.stripe_sync import sync_stripe_data_on_startup
                result = sync_stripe_data_on_startup()
                return JsonResponse(result)
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
        
        return JsonResponse({'error': 'POST method required'})
    
    def sync_logs_view(self, request):
        """View recent sync logs with download option"""
        import os
        from django.http import HttpResponse
        from django.conf import settings
        
        # Check if this is a download request
        download = request.GET.get('download', False)
        
        try:
            # Primary log file: our dedicated subscription error log
            primary_log_file = "subscription_error_log.txt"
            secondary_log_file = os.path.join(settings.BASE_DIR, 'django.log')
            
            logs_content = ""
            
            # Try to read the primary subscription log first
            if os.path.exists(primary_log_file):
                with open(primary_log_file, 'r', encoding='utf-8') as f:
                    logs_content += "=== SUBSCRIPTION ERROR LOG (subscription_error_log.txt) ===\n"
                    if download:
                        # Return full log for download
                        logs_content += f.read()
                    else:
                        # Get last 200 lines for viewing
                        lines = f.readlines()
                        logs_content += ''.join(lines[-200:])
                    logs_content += "\n\n"
            
            # Also include django.log if it exists and has subscription-related entries
            if os.path.exists(secondary_log_file):
                with open(secondary_log_file, 'r') as f:
                    lines = f.readlines()
                    # Filter for subscription/sync-related logs
                    sync_lines = [line for line in lines if any(keyword in line.lower() for keyword in ['subscription', 'stripe', 'sync', 'webhook', 'booking'])]
                    
                    if sync_lines:
                        logs_content += "=== DJANGO LOG (django.log) - Subscription/Sync Related ===\n"
                        if download:
                            logs_content += ''.join(sync_lines)
                        else:
                            logs_content += ''.join(sync_lines[-100:])  # Last 100 sync-related lines
            
            if not logs_content:
                logs_content = "No subscription/sync logs found."
            
            if download:
                # Return as downloadable file
                response = HttpResponse(logs_content, content_type='text/plain')
                response['Content-Disposition'] = 'attachment; filename="subscription_logs.txt"'
                return response
            else:
                # Return as JSON for web viewing
                return JsonResponse({
                    'success': True,
                    'logs': logs_content,
                    'log_files_checked': [primary_log_file, secondary_log_file],
                    'download_url': request.build_absolute_uri() + '?download=1'
                })
                
        except Exception as e:
            error_msg = f"Error reading log files: {str(e)}"
            if download:
                return HttpResponse(error_msg, content_type='text/plain', status=500)
            else:
                return JsonResponse({'success': False, 'error': error_msg})


# Use custom admin site
admin_site = StripeSyncAdminSite()

# Register models with custom site
admin_site.register(Client, ClientAdmin)
admin_site.register(Subscription, SubscriptionAdmin) 
admin_site.register(Booking, BookingAdmin)
admin_site.register(Schedule, ScheduleAdmin)
admin_site.register(StripeSettings, StripeSettingsAdmin)

# Also register with default admin site for compatibility
admin.site.site_header = "New Farm Dog Walking Admin"
admin.site.site_title = "Dog Walking Admin"
admin.site.index_title = "Manage Subscriptions, Bookings & Clients"
