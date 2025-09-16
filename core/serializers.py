"""
Django REST Framework serializers for the dog walking app.

These serializers handle the conversion between Django model instances
and JSON representations for the REST API endpoints.
"""

from rest_framework import serializers
from django.utils import timezone
from .models import Client, Subscription, Booking, Schedule


class ClientSerializer(serializers.ModelSerializer):
    """Serializer for Client model"""
    credit_dollars = serializers.ReadOnlyField()
    total_revenue_dollars = serializers.ReadOnlyField()
    
    class Meta:
        model = Client
        fields = [
            'id', 'name', 'email', 'phone', 'address', 'stripe_customer_id',
            'credit_cents', 'credit_dollars', 'status', 'acquisition_date',
            'last_service_date', 'total_revenue_cents', 'total_revenue_dollars',
            'service_count', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'stripe_customer_id', 'total_revenue_cents', 'service_count',
            'created_at', 'updated_at'
        ]


class SubscriptionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for subscription lists"""
    client_name = serializers.CharField(source='client.name', read_only=True)
    schedule_duration_display = serializers.SerializerMethodField()
    next_occurrence = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'stripe_subscription_id', 'client', 'client_name', 'status',
            'service_code', 'service_name', 'schedule_days', 'schedule_start_time',
            'schedule_end_time', 'schedule_duration_display', 'schedule_location',
            'schedule_dogs', 'next_occurrence', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'stripe_subscription_id', 'created_from_stripe', 'stripe_created_at',
            'last_sync_at', 'created_at', 'updated_at'
        ]

    def get_schedule_duration_display(self, obj):
        """Return schedule duration as string"""
        return str(obj.schedule_duration)

    def get_next_occurrence(self, obj):
        """Return next occurrence date"""
        next_date = obj.get_next_occurrence()
        return next_date.isoformat() if next_date else None


class SubscriptionDetailSerializer(SubscriptionListSerializer):
    """Detailed serializer for individual subscription views"""
    schedule_days_list = serializers.ReadOnlyField()
    bookings_count = serializers.SerializerMethodField()
    
    class Meta(SubscriptionListSerializer.Meta):
        fields = SubscriptionListSerializer.Meta.fields + [
            'schedule_days_list', 'schedule_notes', 'created_from_stripe',
            'stripe_created_at', 'last_sync_at', 'bookings_count'
        ]

    def get_bookings_count(self, obj):
        """Return number of bookings for this subscription"""
        return obj.bookings.count()


class BookingListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for booking lists"""
    client_name = serializers.CharField(source='client.name', read_only=True)
    subscription_id = serializers.CharField(source='subscription.stripe_subscription_id', read_only=True)
    duration_display = serializers.SerializerMethodField()
    is_today = serializers.ReadOnlyField()
    is_upcoming = serializers.ReadOnlyField()
    
    class Meta:
        model = Booking
        fields = [
            'id', 'client', 'client_name', 'subscription', 'subscription_id',
            'start_dt', 'end_dt', 'duration_display', 'service_type', 'service_name',
            'location', 'dogs', 'status', 'source', 'is_today', 'is_upcoming',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_duration_display(self, obj):
        """Return duration as string"""
        return str(obj.duration)


class BookingDetailSerializer(BookingListSerializer):
    """Detailed serializer for individual booking views"""
    can_be_invoiced = serializers.ReadOnlyField()
    has_invoice = serializers.SerializerMethodField()
    
    class Meta(BookingListSerializer.Meta):
        fields = BookingListSerializer.Meta.fields + [
            'notes', 'created_from_sub_id', 'stripe_invoice_id',
            'stripe_price_id', 'invoice_url', 'can_be_invoiced', 'has_invoice'
        ]
        read_only_fields = BookingListSerializer.Meta.read_only_fields + [
            'created_from_sub_id', 'stripe_invoice_id', 'stripe_price_id'
        ]

    def get_has_invoice(self, obj):
        """Return whether booking has an invoice"""
        return bool(obj.stripe_invoice_id)


class BookingCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating bookings"""
    
    class Meta:
        model = Booking
        fields = [
            'client', 'start_dt', 'end_dt', 'service_type', 'service_name',
            'location', 'dogs', 'notes', 'status'
        ]

    def validate(self, attrs):
        """Validate booking data"""
        start_dt = attrs.get('start_dt')
        end_dt = attrs.get('end_dt')
        
        if start_dt and end_dt:
            if end_dt <= start_dt:
                raise serializers.ValidationError(
                    "End time must be after start time"
                )
            
            # Check for overlapping bookings for the same client
            client = attrs.get('client')
            if client:
                overlapping = Booking.objects.filter(
                    client=client,
                    start_dt__lt=end_dt,
                    end_dt__gt=start_dt,
                    status__in=['scheduled', 'confirmed', 'in_progress']
                )
                
                # Exclude current instance if updating
                if self.instance:
                    overlapping = overlapping.exclude(id=self.instance.id)
                
                if overlapping.exists():
                    raise serializers.ValidationError(
                        "Client has overlapping booking during this time"
                    )
        
        return attrs


class ScheduleSerializer(serializers.ModelSerializer):
    """Serializer for Schedule model"""
    days_list = serializers.ReadOnlyField()
    days_display = serializers.SerializerMethodField()
    time_range = serializers.SerializerMethodField()
    
    class Meta:
        model = Schedule
        fields = [
            'id', 'name', 'description', 'days_of_week', 'days_list', 'days_display',
            'start_time', 'end_time', 'time_range', 'service_code', 'default_location',
            'default_dogs', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_days_display(self, obj):
        """Return days in readable format"""
        days_map = {
            0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu',
            4: 'Fri', 5: 'Sat', 6: 'Sun'
        }
        days = obj.days_list
        return ', '.join(days_map.get(day, str(day)) for day in days)

    def get_time_range(self, obj):
        """Return time range as string"""
        return f"{obj.start_time} - {obj.end_time}"


class SubscriptionSyncSerializer(serializers.Serializer):
    """Serializer for subscription sync operations"""
    subscription_ids = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        help_text="List of Stripe subscription IDs to sync. If empty, sync all active subscriptions."
    )
    horizon_days = serializers.IntegerField(
        default=90,
        min_value=1,
        max_value=365,
        help_text="Number of days ahead to generate bookings"
    )
    force_update = serializers.BooleanField(
        default=False,
        help_text="Force update of existing bookings"
    )


class BookingGenerationSerializer(serializers.Serializer):
    """Serializer for booking generation operations"""
    subscription_id = serializers.CharField(max_length=100)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    
    def validate(self, attrs):
        """Validate date range"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if end_date <= start_date:
                raise serializers.ValidationError(
                    "End date must be after start date"
                )
            
            # Reasonable limits
            if (end_date - start_date).days > 365:
                raise serializers.ValidationError(
                    "Date range cannot exceed 365 days"
                )
        
        return attrs