"""Core subscription sync functionality to materialize Stripe subscriptions to SubOccurrence."""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import stripe

from django.utils import timezone as django_tz
from .models import SubOccurrence
from .stripe_integration import get_api_key, list_active_subscriptions
from .log_utils import log_subscription_error, log_subscription_info


def _get_fake_subscriptions() -> List[Dict]:
    """Generate fake subscription data for when Stripe is not configured.
    
    Returns:
        List of fake subscription dictionaries mimicking Stripe subscription structure
    """
    base_time = django_tz.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    return [
        {
            'id': 'sub_fake_weekly_walk_001',
            'status': 'active',
            'current_period_start': int(base_time.timestamp()),
            'current_period_end': int((base_time + timedelta(days=7)).timestamp()),
            'plan': {
                'interval': 'week',
                'interval_count': 1
            },
            'metadata': {
                'service_type': 'dog_walk',
                'client_id': '1'
            }
        },
        {
            'id': 'sub_fake_biweekly_grooming_002',
            'status': 'active',
            'current_period_start': int(base_time.timestamp()),
            'current_period_end': int((base_time + timedelta(days=14)).timestamp()),
            'plan': {
                'interval': 'week',
                'interval_count': 2
            },
            'metadata': {
                'service_type': 'grooming',
                'client_id': '2'
            }
        },
        {
            'id': 'sub_fake_monthly_sitting_003',
            'status': 'active',
            'current_period_start': int(base_time.timestamp()),
            'current_period_end': int((base_time + timedelta(days=30)).timestamp()),
            'plan': {
                'interval': 'month',
                'interval_count': 1
            },
            'metadata': {
                'service_type': 'pet_sitting',
                'client_id': '3'
            }
        }
    ]


def _expand_subscription_occurrences(subscription_data: Dict, horizon_days: int) -> List[Dict]:
    """Expand a single subscription into multiple occurrences within the horizon.
    
    Args:
        subscription_data: Stripe subscription data dictionary
        horizon_days: Number of days to look ahead
        
    Returns:
        List of occurrence dictionaries with start_dt and end_dt
    """
    occurrences = []
    
    # Parse subscription timing
    plan = subscription_data.get('plan', {})
    interval = plan.get('interval', 'month')  # day, week, month, year
    interval_count = plan.get('interval_count', 1)
    
    # Calculate interval in days
    if interval == 'day':
        interval_days = interval_count
    elif interval == 'week':
        interval_days = interval_count * 7
    elif interval == 'month':
        interval_days = interval_count * 30  # Approximate
    elif interval == 'year':
        interval_days = interval_count * 365  # Approximate
    else:
        log_subscription_error(f"Unknown interval '{interval}' for subscription {subscription_data['id']}")
        interval_days = 30  # Default fallback
    
    # Start from current period start
    current_start_ts = subscription_data.get('current_period_start', int(django_tz.now().timestamp()))
    current_start = datetime.fromtimestamp(current_start_ts, tz=timezone.utc)
    
    # Generate occurrences within horizon
    today = django_tz.now().date()
    horizon_date = today + timedelta(days=horizon_days)
    
    occurrence_start = current_start
    while occurrence_start.date() <= horizon_date:
        occurrence_end = occurrence_start + timedelta(days=interval_days)
        
        # Only include occurrences that start today or in the future
        if occurrence_start.date() >= today:
            occurrences.append({
                'subscription_id': subscription_data['id'],
                'start_dt': occurrence_start,
                'end_dt': occurrence_end,
                'active': subscription_data.get('status') == 'active'
            })
        
        occurrence_start = occurrence_end
    
    return occurrences


def _get_active_subscriptions(horizon_days: int) -> List[Dict]:
    """Get active subscriptions from Stripe or return fake data if not configured.
    
    Args:
        horizon_days: Number of days to look ahead for subscription data
        
    Returns:
        List of subscription dictionaries
    """
    try:
        # Try to get real Stripe subscriptions
        api_key = get_api_key()
        if not api_key:
            log_subscription_info("Stripe API key not configured, using fake subscription data")
            return _get_fake_subscriptions()
        
        # Get active subscriptions from Stripe
        subscriptions = list_active_subscriptions(
            status='active',
            limit=100  # Adjust limit as needed
        )
        
        subscription_list = []
        for sub in subscriptions.auto_paging_iter():
            # Convert Stripe object to dict-like structure
            subscription_list.append({
                'id': sub.id,
                'status': sub.status,
                'current_period_start': sub.current_period_start,
                'current_period_end': sub.current_period_end,
                'plan': {
                    'interval': sub.plan.interval,
                    'interval_count': sub.plan.interval_count
                },
                'metadata': dict(sub.metadata) if sub.metadata else {}
            })
        
        log_subscription_info(f"Retrieved {len(subscription_list)} active subscriptions from Stripe")
        return subscription_list
        
    except Exception as e:
        log_subscription_error(f"Error fetching Stripe subscriptions: {e}")
        log_subscription_info("Falling back to fake subscription data")
        return _get_fake_subscriptions()


def sync_subscriptions_to_bookings_and_calendar(horizon_days: int = 90) -> Dict:
    """Clear future SubOccurrence (>= today) then rebuild from active Stripe subscriptions.
    
    Args:
        horizon_days: Number of days to look ahead for creating subscription occurrences
        
    Returns:
        Dict with keys: processed, created, cleaned, errors
    """
    result = {
        'processed': 0,
        'created': 0,
        'cleaned': 0,
        'errors': 0
    }
    
    log_subscription_info(f"Starting subscription sync with horizon_days={horizon_days}")
    
    try:
        # Step 1: Clear future SubOccurrence records (>= today)
        today = django_tz.now().date()
        future_occurrences = SubOccurrence.objects.filter(start_dt__date__gte=today)
        cleaned_count = future_occurrences.count()
        future_occurrences.delete()
        result['cleaned'] = cleaned_count
        
        log_subscription_info(f"Cleaned {cleaned_count} future SubOccurrence records")
        
        # Step 2: Get active subscriptions
        subscriptions = _get_active_subscriptions(horizon_days)
        result['processed'] = len(subscriptions)
        
        # Step 3: Generate and create new SubOccurrence records
        for subscription in subscriptions:
            try:
                occurrences = _expand_subscription_occurrences(subscription, horizon_days)
                
                for occurrence in occurrences:
                    SubOccurrence.objects.create(
                        stripe_subscription_id=occurrence['subscription_id'],
                        start_dt=occurrence['start_dt'],
                        end_dt=occurrence['end_dt'],
                        active=occurrence['active']
                    )
                    result['created'] += 1
                
                log_subscription_info(
                    f"Created {len(occurrences)} occurrences for subscription {subscription['id']}"
                )
                
            except Exception as e:
                log_subscription_error(f"Error processing subscription {subscription.get('id', 'unknown')}: {e}")
                result['errors'] += 1
        
        log_subscription_info(
            f"Sync completed: processed={result['processed']}, "
            f"created={result['created']}, cleaned={result['cleaned']}, errors={result['errors']}"
        )
        
    except Exception as e:
        log_subscription_error(f"Critical error in subscription sync: {e}")
        result['errors'] += 1
    
    return result