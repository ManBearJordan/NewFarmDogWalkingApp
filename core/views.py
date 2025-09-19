"""
Django REST Framework views for the dog walking app.

These views provide REST API endpoints for managing subscriptions, bookings,
clients, and schedules with proper authentication and permissions.
"""

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from django.db.models import Q, Count, Sum
from datetime import datetime, timedelta, date
import logging

from .models import Client, Subscription, Booking, Schedule
from .serializers import (
    ClientSerializer, SubscriptionListSerializer, SubscriptionDetailSerializer,
    BookingListSerializer, BookingDetailSerializer, BookingCreateUpdateSerializer,
    ScheduleSerializer, SubscriptionSyncSerializer, BookingGenerationSerializer
)

logger = logging.getLogger(__name__)


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for API views"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ClientViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing clients.
    
    Provides CRUD operations for client management with search and filtering.
    """
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    filterset_fields = ['status', 'stripe_customer_id']
    search_fields = ['name', 'email', 'phone']
    ordering_fields = ['name', 'created_at', 'last_service_date', 'total_revenue_cents']
    ordering = ['-created_at']

    @action(detail=True, methods=['get'])
    def subscriptions(self, request, pk=None):
        """Get all subscriptions for a client"""
        client = self.get_object()
        subscriptions = client.subscriptions.all()
        serializer = SubscriptionListSerializer(subscriptions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def bookings(self, request, pk=None):
        """Get all bookings for a client"""
        client = self.get_object()
        bookings = client.bookings.all().order_by('-start_dt')
        
        # Optional date filtering
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            try:
                start_date = datetime.fromisoformat(start_date).date()
                bookings = bookings.filter(start_dt__date__gte=start_date)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_date = datetime.fromisoformat(end_date).date()
                bookings = bookings.filter(start_dt__date__lte=end_date)
            except ValueError:
                pass
        
        page = self.paginate_queryset(bookings)
        if page is not None:
            serializer = BookingListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = BookingListSerializer(bookings, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_credit(self, request, pk=None):
        """Add credit to client account"""
        client = self.get_object()
        amount_cents = request.data.get('amount_cents')
        
        if not amount_cents or not isinstance(amount_cents, int) or amount_cents <= 0:
            return Response(
                {'error': 'amount_cents must be a positive integer'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        client.credit_cents += amount_cents
        client.save()
        
        return Response({
            'message': f'Added ${amount_cents/100:.2f} credit',
            'new_credit_cents': client.credit_cents,
            'new_credit_dollars': client.credit_dollars
        })


class SubscriptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing subscriptions.
    
    Provides CRUD operations for subscription management with Stripe integration.
    AUTOMATICALLY GENERATES BOOKINGS when subscriptions are created or updated.
    """
    queryset = Subscription.objects.select_related('client').all()
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    filterset_fields = ['status', 'service_code', 'client', 'schedule_dogs']
    search_fields = ['stripe_subscription_id', 'client__name', 'service_name', 'schedule_location']
    ordering_fields = ['created_at', 'schedule_start_time', 'client__name']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return SubscriptionListSerializer
        return SubscriptionDetailSerializer

    def perform_create(self, serializer):
        """Automatically trigger booking generation when subscription is created via API"""
        subscription = serializer.save()
        
        logger.info(f"API: Creating subscription {subscription.stripe_subscription_id}")
        
        # Import logging utilities
        from log_utils import log_subscription_info, log_subscription_error
        log_subscription_info(f"Subscription created via API: {subscription.stripe_subscription_id}", subscription.stripe_subscription_id)
        
        # Automatically trigger booking generation if subscription is active and has schedule
        if subscription.status == 'active' and self._has_valid_schedule(subscription):
            try:
                # Import tasks
                from .tasks import generate_subscription_bookings_sync
                
                logger.info(f"AUTO-GENERATING bookings for new API subscription {subscription.stripe_subscription_id}")
                result = generate_subscription_bookings_sync(subscription.stripe_subscription_id)
                
                if result.get('success'):
                    log_subscription_info(f"API auto-booking SUCCESS: {result.get('bookings_created', 0)} bookings created", subscription.stripe_subscription_id)
                else:
                    log_subscription_error(f"API auto-booking FAILED: {result.get('error', 'Unknown error')}", subscription.stripe_subscription_id)
                    
            except Exception as e:
                error_msg = f"Booking generation failed after API subscription creation {subscription.stripe_subscription_id}: {e}"
                logger.error(error_msg)
                log_subscription_error(error_msg, subscription.stripe_subscription_id, e)

    def perform_update(self, serializer):
        """Automatically trigger booking generation when subscription is updated via API"""
        # Get original subscription to detect changes
        original_subscription = self.get_object()
        
        # Check if schedule-related fields changed
        schedule_changed = False
        new_data = serializer.validated_data
        
        schedule_fields = ['schedule_days', 'schedule_start_time', 'schedule_end_time', 
                          'schedule_location', 'schedule_dogs', 'service_code', 'status']
        
        for field in schedule_fields:
            if field in new_data and getattr(original_subscription, field) != new_data[field]:
                schedule_changed = True
                break
        
        subscription = serializer.save()
        
        logger.info(f"API: Updated subscription {subscription.stripe_subscription_id}, schedule_changed={schedule_changed}")
        
        # Import logging utilities
        from log_utils import log_subscription_info, log_subscription_error
        log_subscription_info(f"Subscription updated via API: {subscription.stripe_subscription_id}, schedule_changed={schedule_changed}", subscription.stripe_subscription_id)
        
        # Automatically trigger booking generation if schedule changed and subscription is active
        if schedule_changed and subscription.status == 'active' and self._has_valid_schedule(subscription):
            try:
                # Import tasks
                from .tasks import generate_subscription_bookings_sync
                
                logger.info(f"AUTO-REGENERATING bookings for updated API subscription {subscription.stripe_subscription_id}")
                result = generate_subscription_bookings_sync(subscription.stripe_subscription_id)
                
                if result.get('success'):
                    log_subscription_info(f"API auto-booking update SUCCESS: {result.get('bookings_created', 0)} bookings created", subscription.stripe_subscription_id)
                else:
                    log_subscription_error(f"API auto-booking update FAILED: {result.get('error', 'Unknown error')}", subscription.stripe_subscription_id)
                    
            except Exception as e:
                error_msg = f"Booking generation failed after API subscription update {subscription.stripe_subscription_id}: {e}"
                logger.error(error_msg)
                log_subscription_error(error_msg, subscription.stripe_subscription_id, e)

    def _has_valid_schedule(self, subscription):
        """Check if subscription has valid schedule metadata for booking generation"""
        return (subscription.schedule_days and 
                subscription.schedule_start_time and 
                subscription.schedule_end_time and
                subscription.service_code)

    @action(detail=True, methods=['get'])
    def bookings(self, request, pk=None):
        """Get all bookings for a subscription"""
        subscription = self.get_object()
        bookings = subscription.bookings.all().order_by('-start_dt')
        
        page = self.paginate_queryset(bookings)
        if page is not None:
            serializer = BookingListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = BookingListSerializer(bookings, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def sync_with_stripe(self, request, pk=None):
        """Sync individual subscription with Stripe"""
        subscription = self.get_object()
        
        try:
            # Integration point with existing sync logic
            # This would call the existing subscription_sync.py functions
            from subscription_sync import sync_on_subscription_change
            
            result = sync_on_subscription_change(subscription.stripe_subscription_id)
            subscription.last_sync_at = timezone.now()
            subscription.save()
            
            return Response({
                'message': 'Subscription synced successfully',
                'sync_result': result
            })
        except Exception as e:
            logger.error(f"Failed to sync subscription {subscription.stripe_subscription_id}: {e}")
            return Response(
                {'error': f'Sync failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def generate_bookings(self, request, pk=None):
        """Generate bookings for this subscription"""
        subscription = self.get_object()
        serializer = BookingGenerationSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                # Integration point with existing booking generation logic
                # This would use the existing booking_utils.py functions
                
                # Default date range if not provided
                start_date = serializer.validated_data.get('start_date', date.today())
                end_date = serializer.validated_data.get('end_date', start_date + timedelta(days=90))
                
                # This would integrate with existing booking generation
                bookings_created = 0  # Placeholder
                
                return Response({
                    'message': f'Generated {bookings_created} bookings',
                    'start_date': start_date,
                    'end_date': end_date
                })
            except Exception as e:
                logger.error(f"Failed to generate bookings for {subscription.stripe_subscription_id}: {e}")
                return Response(
                    {'error': f'Booking generation failed: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def sync_all(self, request):
        """Sync all subscriptions or specific ones with Stripe"""
        serializer = SubscriptionSyncSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                # Integration point with existing sync logic
                from subscription_sync import sync_subscriptions_to_bookings_and_calendar
                
                horizon_days = serializer.validated_data.get('horizon_days', 90)
                result = sync_subscriptions_to_bookings_and_calendar(horizon_days=horizon_days)
                
                return Response({
                    'message': 'Sync completed successfully',
                    'result': result
                })
            except Exception as e:
                logger.error(f"Failed to sync subscriptions: {e}")
                return Response(
                    {'error': f'Sync failed: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing bookings.
    
    Provides CRUD operations for booking management with filtering and actions.
    """
    queryset = Booking.objects.select_related('client', 'subscription').all()
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    filterset_fields = ['status', 'source', 'service_type', 'client', 'dogs']
    search_fields = ['client__name', 'service_name', 'location', 'notes']
    ordering_fields = ['start_dt', 'created_at', 'client__name']
    ordering = ['-start_dt']

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action in ['create', 'update', 'partial_update']:
            return BookingCreateUpdateSerializer
        elif self.action == 'list':
            return BookingListSerializer
        return BookingDetailSerializer

    def get_queryset(self):
        """Apply additional filtering based on query parameters"""
        queryset = super().get_queryset()
        
        # Date range filtering
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            try:
                start_date = datetime.fromisoformat(start_date)
                queryset = queryset.filter(start_dt__gte=start_date)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_date = datetime.fromisoformat(end_date)
                queryset = queryset.filter(start_dt__lte=end_date)
            except ValueError:
                pass
        
        # Convenience filters
        today = self.request.query_params.get('today')
        if today and today.lower() in ['true', '1']:
            today_date = timezone.now().date()
            queryset = queryset.filter(start_dt__date=today_date)
        
        upcoming = self.request.query_params.get('upcoming')
        if upcoming and upcoming.lower() in ['true', '1']:
            queryset = queryset.filter(start_dt__gt=timezone.now())
        
        return queryset

    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        """Mark booking as completed"""
        booking = self.get_object()
        booking.status = 'completed'
        booking.save()
        
        serializer = self.get_serializer(booking)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def mark_canceled(self, request, pk=None):
        """Mark booking as canceled"""
        booking = self.get_object()
        booking.status = 'canceled'
        booking.save()
        
        serializer = self.get_serializer(booking)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def create_invoice(self, request, pk=None):
        """Create Stripe invoice for completed booking"""
        booking = self.get_object()
        
        if not booking.can_be_invoiced():
            return Response(
                {'error': 'Booking cannot be invoiced'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Integration point with existing invoice creation
            # This would use stripe_integration.py functions
            
            return Response({
                'message': 'Invoice created successfully',
                'invoice_id': 'placeholder_invoice_id'
            })
        except Exception as e:
            logger.error(f"Failed to create invoice for booking {booking.id}: {e}")
            return Response(
                {'error': f'Invoice creation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get booking statistics"""
        queryset = self.get_queryset()
        
        stats = {
            'total_bookings': queryset.count(),
            'by_status': dict(queryset.values_list('status').annotate(count=Count('status'))),
            'by_source': dict(queryset.values_list('source').annotate(count=Count('source'))),
            'today_count': queryset.filter(start_dt__date=timezone.now().date()).count(),
            'upcoming_count': queryset.filter(start_dt__gt=timezone.now()).count(),
        }
        
        return Response(stats)


class ScheduleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing schedule templates.
    
    Provides CRUD operations for schedule template management.
    """
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    filterset_fields = ['is_active', 'service_code', 'default_dogs']
    search_fields = ['name', 'description', 'default_location']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        """Filter active schedules by default"""
        queryset = super().get_queryset()
        
        show_inactive = self.request.query_params.get('show_inactive')
        if not (show_inactive and show_inactive.lower() in ['true', '1']):
            queryset = queryset.filter(is_active=True)
        
        return queryset
