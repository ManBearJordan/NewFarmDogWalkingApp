"""
Automatic subscription sync on app startup and Stripe data changes.

This module implements the automated subscription sync workflow that:
1. Runs automatically when the app starts
2. Processes all active subscriptions from Stripe
3. Shows modal popups for subscriptions missing schedule data
4. Updates both local database and Stripe metadata when info is saved
5. Generates bookings and calendar entries immediately after schedule completion
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from PySide6.QtWidgets import QWidget, QMessageBox, QApplication, QDialog
from PySide6.QtCore import QObject, Signal, QTimer, QThread, Qt

# Import our new modules
from subscription_validator import (
    get_subscriptions_missing_schedule_data,
    update_stripe_subscription_metadata, 
    update_local_subscription_schedule
)
from subscription_schedule_dialog import show_subscription_schedule_dialogs
from subscription_sync import sync_subscriptions_to_bookings_and_calendar
import sqlite3

logger = logging.getLogger(__name__)


class SubscriptionAutoSync(QObject):
    """
    Handles automatic subscription synchronization and schedule completion.
    """
    
    sync_started = Signal()
    sync_completed = Signal(dict)  # stats
    schedule_dialogs_needed = Signal(list)  # subscriptions_missing_data
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.conn = None
    
    def set_connection(self, conn: sqlite3.Connection):
        """Set database connection."""
        self.conn = conn
    
    def perform_startup_sync(self, show_progress: bool = True) -> Dict[str, Any]:
        """
        Perform complete startup sync workflow.
        
        This is the main entry point for automatic subscription sync.
        ENHANCED: Comprehensive error logging with zero silent failures.
        
        Args:
            show_progress: Whether to show progress dialogs
            
        Returns:
            Dictionary with sync results and statistics
        """
        try:
            from log_utils import log_subscription_info, log_subscription_error
            
            logger.info("Starting automatic subscription sync on startup")
            log_subscription_info("Startup sync initiated")
            log_subscription_info("STARTUP SYNC: Beginning automatic subscription sync")
            
            if show_progress:
                self.sync_started.emit()
            
            # STARTUP STEP 1: Get all active subscriptions from Stripe
            log_subscription_info("STARTUP STEP 1: Fetching active subscriptions from Stripe")
            try:
                from stripe_integration import list_active_subscriptions
                
                logger.info("Fetching active subscriptions from Stripe")
                subscriptions = list_active_subscriptions()
                log_subscription_info(f"STARTUP STEP 1 SUCCESS: Retrieved {len(subscriptions)} active subscriptions")
            except Exception as e:
                error_msg = f"STARTUP STEP 1 FAILED: Failed to fetch active subscriptions from Stripe: {e}"
                logger.error(error_msg)
                log_subscription_error(error_msg, "startup_sync", e)
                raise
            
            if not subscriptions:
                logger.info("No active subscriptions found")
                log_subscription_info("STARTUP SYNC COMPLETE: No active subscriptions found")
                results = {
                    "total_subscriptions": 0,
                    "missing_schedule_count": 0,
                    "completed_schedules": 0,
                    "sync_stats": {"subscriptions_processed": 0, "bookings_created": 0, "bookings_cleaned": 0, "errors_count": 0}
                }
                if show_progress:
                    self.sync_completed.emit(results)
                return results
            
            # STARTUP STEP 2: Identify subscriptions missing schedule data
            log_subscription_info(f"STARTUP STEP 2: Analyzing {len(subscriptions)} subscriptions for missing schedule data")
            logger.info(f"Analyzing {len(subscriptions)} subscriptions for missing schedule data")
            
            try:
                missing_data_subscriptions = get_subscriptions_missing_schedule_data(subscriptions)
                log_subscription_info(f"STARTUP STEP 2 SUCCESS: Found {len(missing_data_subscriptions)} subscriptions missing schedule data")
                logger.info(f"Found {len(missing_data_subscriptions)} subscriptions missing schedule data")
            except Exception as e:
                error_msg = f"STARTUP STEP 2 FAILED: Failed to analyze subscription schedule data: {e}"
                logger.error(error_msg)
                log_subscription_error(error_msg, "startup_sync", e)
                # Continue with sync even if schedule analysis fails
                missing_data_subscriptions = []
            
            # STARTUP STEP 3: Show modal dialogs for missing data (if any)
            completed_schedules = []
            if missing_data_subscriptions:
                log_subscription_info(f"STARTUP STEP 3: Showing schedule completion dialogs for {len(missing_data_subscriptions)} subscriptions")
                logger.info("Showing schedule completion dialogs")
                self.schedule_dialogs_needed.emit(missing_data_subscriptions)
                
                # This will be handled by the UI thread showing dialogs
                # For now, we'll continue with the sync
            else:
                log_subscription_info("STARTUP STEP 3: No schedule dialogs needed - all subscriptions have complete data")
            
            # STARTUP STEP 4: Perform the main subscription sync
            log_subscription_info("STARTUP STEP 4: Performing subscription sync to generate bookings and calendar")
            logger.info("Performing subscription sync to generate bookings and calendar")
            
            try:
                sync_stats = sync_subscriptions_to_bookings_and_calendar(self.conn)
                
                # Ensure error count is included in stats
                if 'errors_count' not in sync_stats:
                    sync_stats['errors_count'] = 0
                    
                log_subscription_info(f"Main sync completed: {sync_stats.get('bookings_created', 0)} bookings created, {sync_stats.get('errors_count', 0)} errors")
                
            except Exception as e:
                error_msg = f"Main subscription sync failed: {e}"
                logger.error(error_msg)
                log_subscription_error(error_msg, "startup_sync", e)
                # Set error stats
                sync_stats = {
                    "subscriptions_processed": 0,
                    "bookings_created": 0, 
                    "bookings_cleaned": 0,
                    "errors_count": 1,
                    "error": str(e)
                }
            
            # Compile results
            results = {
                "total_subscriptions": len(subscriptions),
                "missing_schedule_count": len(missing_data_subscriptions),
                "completed_schedules": len(completed_schedules),
                "sync_stats": sync_stats,
                "missing_data_subscriptions": missing_data_subscriptions
            }
            
            logger.info(f"Startup sync completed: {results}")
            log_subscription_info(f"Startup sync completed: {results['total_subscriptions']} subs, {sync_stats.get('bookings_created', 0)} bookings, {sync_stats.get('errors_count', 0)} errors")
            
            if show_progress:
                self.sync_completed.emit(results)
            
            return results
            
        except Exception as e:
            error_msg = f"Startup sync failed: {e}"
            logger.error(error_msg)
            log_subscription_error(error_msg, "startup_sync", e)
            
            error_results = {
                "error": str(e),
                "total_subscriptions": 0,
                "missing_schedule_count": 0,
                "completed_schedules": 0,
                "sync_stats": {"subscriptions_processed": 0, "bookings_created": 0, "bookings_cleaned": 0, "errors_count": 1}
            }
            if show_progress:
                self.sync_completed.emit(error_results)
            return error_results
    
    def handle_schedule_completion(self, subscription_id: str, schedule_data: Dict[str, Any], parent_widget=None) -> bool:
        """
        Handle completion of schedule data for a subscription with enhanced error handling.
        
        This updates both Stripe metadata and local database, then triggers
        immediate booking generation for the specific subscription.
        
        Args:
            subscription_id: Stripe subscription ID
            schedule_data: Dictionary with schedule information
            parent_widget: Parent widget for showing error dialogs
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Processing completed schedule for subscription {subscription_id}")
            logger.debug(f"Schedule data received: {schedule_data}")
            
            # Validate required fields
            required_fields = ["days", "start_time", "end_time", "location", "dogs"]
            missing_fields = [field for field in required_fields if not schedule_data.get(field)]
            
            if missing_fields:
                error_msg = f"Missing required schedule fields: {', '.join(missing_fields)}"
                logger.error(f"Schedule validation failed for {subscription_id}: {error_msg}")
                logger.debug(f"Available fields: {list(schedule_data.keys())}")
                
                if parent_widget:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(
                        parent_widget,
                        "Schedule Data Error", 
                        f"Cannot save schedule - {error_msg}"
                    )
                return False
            
            logger.info(f"Schedule validation passed for {subscription_id}. Processing {len(schedule_data.get('days', '').split(','))} days: {schedule_data.get('days')}")
            
            # Additional validation: Check for common metadata naming issues
            metadata_warnings = []
            if 'booking_start' in str(schedule_data).lower() or 'booking_time' in str(schedule_data).lower():
                metadata_warnings.append("Found 'booking_start' or 'booking_time' fields - ensure metadata uses 'start_time' not 'booking_start'")
            if 'booking_end' in str(schedule_data).lower():
                metadata_warnings.append("Found 'booking_end' fields - ensure metadata uses 'end_time' not 'booking_end'")
            
            if metadata_warnings:
                logger.warning(f"Metadata naming warnings for {subscription_id}: {'; '.join(metadata_warnings)}")
                
            # Validate time format
            try:
                from datetime import datetime
                datetime.strptime(schedule_data['start_time'], '%H:%M')
                datetime.strptime(schedule_data['end_time'], '%H:%M')
                logger.debug(f"Time format validation passed: {schedule_data['start_time']} - {schedule_data['end_time']}")
            except ValueError as time_error:
                error_msg = f"Invalid time format in schedule data: {time_error}"
                logger.error(f"❌ {error_msg}")
                if parent_widget:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(parent_widget, "Time Format Error", error_msg)
                return False
            
            # Step 1: Update Stripe subscription metadata
            logger.info(f"Step 1: Updating Stripe subscription metadata for {subscription_id}")
            logger.debug(f"Metadata to be saved: days='{schedule_data['days']}', time={schedule_data['start_time']}-{schedule_data['end_time']}, location='{schedule_data['location']}', dogs={schedule_data['dogs']}")
            
            success_stripe = update_stripe_subscription_metadata(
                subscription_id,
                schedule_data["days"],
                schedule_data["start_time"],
                schedule_data["end_time"],
                schedule_data["location"],
                schedule_data["dogs"],
                schedule_data.get("notes", ""),
                schedule_data.get("service_code", "")
            )
            
            if success_stripe:
                logger.info(f"✅ Successfully updated Stripe metadata for subscription {subscription_id}")
            else:
                logger.warning(f"⚠️ Failed to update Stripe metadata for {subscription_id} - continuing with local update")
                # Don't fail completely - local update is more important
            
            # Step 2: Update local database (this is critical)
            logger.info(f"Step 2: Updating local database for subscription {subscription_id}")
            success_local = update_local_subscription_schedule(
                self.conn,
                subscription_id,
                schedule_data["days"],
                schedule_data["start_time"],
                schedule_data["end_time"],
                schedule_data["location"],
                schedule_data["dogs"],
                schedule_data.get("notes", ""),
                schedule_data.get("service_code", "")
            )
            
            if success_local:
                logger.info(f"✅ Successfully updated local database for subscription {subscription_id}")
            else:
                error_msg = f"❌ Failed to save schedule to local database for subscription {subscription_id}"
                logger.error(error_msg)
                
                if parent_widget:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.critical(
                        parent_widget,
                        "Database Error",
                        f"Critical error: {error_msg}\n\n" +
                        "Please try saving the schedule again. If this persists, " +
                        "check the application logs for detailed error information."
                    )
                return False
            
            # Step 3: Use unified booking helpers for reliable booking generation
            logger.info(f"Step 3: Generating bookings for subscription {subscription_id} using purge-then-rebuild pattern")
            
            try:
                # Use the unified purge-then-rebuild pattern for reliable booking generation
                from unified_booking_helpers import purge_future_subscription_bookings, rebuild_subscription_bookings
                
                # Convert day list to mask for unified helpers
                days_str = schedule_data["days"]  # e.g., "MON,WED,FRI"
                day_names = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
                days_list = [d.strip().upper() for d in days_str.split(",") if d.strip()]
                days_mask = 0
                for day in days_list:
                    if day in day_names:
                        days_mask |= (1 << day_names.index(day))
                
                logger.debug(f"Days conversion: '{days_str}' -> {days_list} -> mask {days_mask} (binary: {bin(days_mask)})")
                
                # Pre-check: Verify client can be resolved before proceeding
                try:
                    import stripe
                    from secrets_config import get_stripe_key
                    from unified_booking_helpers import resolve_client_id
                    stripe.api_key = get_stripe_key()
                    
                    # Get subscription with customer data
                    subscription = stripe.Subscription.retrieve(subscription_id, expand=['customer'])
                    customer = subscription.customer
                    
                    if hasattr(customer, 'id'):
                        client_id = resolve_client_id(self.conn, customer.id)
                        if not client_id:
                            error_msg = f"Cannot resolve client for subscription {subscription_id}. Customer ID {customer.id} not found in local database."
                            logger.error(f"❌ Client resolution failed: {error_msg}")
                            if parent_widget:
                                from PySide6.QtWidgets import QMessageBox
                                QMessageBox.warning(
                                    parent_widget,
                                    "Client Resolution Error",
                                    f"{error_msg}\n\nPlease ensure the customer exists in your clients database before creating bookings."
                                )
                            return False
                        else:
                            logger.info(f"✅ Client resolution successful: Stripe customer {customer.id} -> local client {client_id}")
                    else:
                        error_msg = f"Invalid customer data in subscription {subscription_id}"
                        logger.error(f"❌ {error_msg}")
                        if parent_widget:
                            from PySide6.QtWidgets import QMessageBox
                            QMessageBox.warning(parent_widget, "Customer Data Error", error_msg)
                        return False
                        
                except Exception as client_check_error:
                    logger.error(f"❌ Client resolution check failed for {subscription_id}: {client_check_error}")
                    if parent_widget:
                        from PySide6.QtWidgets import QMessageBox
                        QMessageBox.warning(
                            parent_widget,
                            "Client Resolution Error", 
                            f"Could not verify client data for subscription {subscription_id}:\n{client_check_error}"
                        )
                    return False
                
                # Step 3a: Purge existing future bookings to avoid conflicts
                logger.info(f"Step 3a: Purging existing future bookings for subscription {subscription_id}")
                purge_future_subscription_bookings(self.conn, subscription_id)
                logger.info(f"✅ Purged existing future bookings for subscription {subscription_id}")
                
                # Step 3b: Rebuild bookings with consistent, unified fields
                logger.info(f"Step 3b: Creating new bookings for next 3 months - time: {schedule_data['start_time']}-{schedule_data['end_time']}, location: '{schedule_data['location']}', dogs: {schedule_data['dogs']}")
                bookings_created = rebuild_subscription_bookings(
                    self.conn,
                    subscription_id,
                    days_mask,
                    schedule_data["start_time"],
                    schedule_data["end_time"],
                    schedule_data["dogs"],
                    schedule_data["location"],
                    schedule_data.get("notes", ""),
                    months_ahead=3
                )
                
                if bookings_created > 0:
                    logger.info(f"✅ Successfully created {bookings_created} bookings for subscription {subscription_id} using unified booking helpers")
                else:
                    logger.warning(f"⚠️ No bookings were created for subscription {subscription_id} - trying fallback method...")
                    
                    # Try the fallback approach if unified helpers failed
                    try:
                        logger.info(f"Attempting fallback booking creation method for {subscription_id}")
                        # Get the updated subscription from Stripe and sync just this one
                        from stripe_integration import _api
                        stripe_api = _api()
                        updated_subscription = stripe_api.Subscription.retrieve(subscription_id, expand=['customer'])
                        
                        # Convert to dict format and ensure customer data
                        subscription_data_dict = dict(updated_subscription)
                        try:
                            from customer_display_helpers import ensure_customer_data_in_subscription
                            subscription_data_dict = ensure_customer_data_in_subscription(subscription_data_dict)
                        except ImportError:
                            logger.warning("customer_display_helpers not available for customer data enhancement")
                        
                        # Fallback to traditional sync approach
                        from subscription_sync import sync_subscription_to_bookings
                        fallback_bookings = sync_subscription_to_bookings(self.conn, subscription_data_dict, parent_widget)
                        
                        if fallback_bookings > 0:
                            logger.info(f"✅ Fallback method created {fallback_bookings} bookings for subscription {subscription_id}")
                            bookings_created = fallback_bookings
                        else:
                            logger.error(f"❌ Both unified and fallback booking generation failed for {subscription_id}")
                            
                    except Exception as fallback_error:
                        logger.error(f"❌ Both unified and fallback booking generation failed for {subscription_id}: {fallback_error}")
                
                # Step 4: Trigger calendar sync to ensure everything is up to date
                logger.info(f"Step 4: Triggering calendar sync to update display")
                try:
                    sync_stats = sync_subscriptions_to_bookings_and_calendar(self.conn)
                    logger.info(f"✅ Calendar sync completed successfully: {sync_stats}")
                except Exception as sync_error:
                    logger.warning(f"⚠️ Calendar sync had issues but continuing: {sync_error}")
                
                logger.info(f"🎉 Schedule completion workflow finished successfully for {subscription_id} - created {bookings_created} bookings")
                return True
                
            except Exception as sync_error:
                from subscription_error_handling import log_subscription_error, handle_stripe_api_error, handle_database_error, show_error_dialog
                
                # Determine error type and provide appropriate handling
                if "stripe" in str(sync_error).lower() or "api" in str(sync_error).lower():
                    user_error_msg = handle_stripe_api_error(sync_error, "booking generation", subscription_id)
                elif "database" in str(sync_error).lower() or "sqlite" in str(sync_error).lower():
                    user_error_msg = handle_database_error(sync_error, "booking generation", subscription_id)
                else:
                    user_error_msg = log_subscription_error("booking generation", subscription_id, sync_error)
                
                if parent_widget:
                    show_error_dialog(
                        parent_widget,
                        "Booking Generation Error",
                        f"Schedule was saved successfully, but there was an error generating bookings:\n\n{user_error_msg}\n\n" +
                        "You can manually refresh bookings from the Subscriptions tab or try completing the schedule again.",
                        details=f"Technical details:\n{str(sync_error)}"
                    )
                
                # Still return True since the schedule was saved successfully - booking generation can be retried
                return True
            
        except Exception as e:
            from subscription_error_handling import log_subscription_error, show_error_dialog
            
            user_error_msg = log_subscription_error("schedule completion", subscription_id, e, {
                "operation": "handle_schedule_completion",
                "schedule_data": schedule_data
            })
            
            if parent_widget:
                show_error_dialog(
                    parent_widget,
                    "Schedule Completion Error",
                    f"An unexpected error occurred while processing the schedule:\n\n{user_error_msg}\n\n" +
                    "Please try saving the schedule again. If this persists, check the application logs for detailed information.",
                    details=f"Technical details:\n{str(e)}"
                )
            return False


class StartupSyncManager(QObject):
    """
    Manages the startup sync process and UI interactions.
    """
    
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.auto_sync = SubscriptionAutoSync()
        
        # Connect signals
        self.auto_sync.sync_started.connect(self.on_sync_started)
        self.auto_sync.sync_completed.connect(self.on_sync_completed)
        self.auto_sync.schedule_dialogs_needed.connect(self.show_schedule_dialogs)
    
    def set_connection(self, conn: sqlite3.Connection):
        """Set database connection."""
        self.auto_sync.set_connection(conn)
    
    def start_automatic_sync(self, delay_ms: int = 1000):
        """
        Start automatic sync after a delay.
        
        Args:
            delay_ms: Delay in milliseconds before starting sync
        """
        logger.info(f"Scheduling automatic sync in {delay_ms}ms")
        QTimer.singleShot(delay_ms, self.perform_sync)
    
    def perform_sync(self):
        """Perform the sync operation."""
        try:
            results = self.auto_sync.perform_startup_sync(show_progress=False)
            
            # If there are subscriptions missing data, show dialogs
            missing_data_subs = results.get("missing_data_subscriptions", [])
            if missing_data_subs:
                self.show_schedule_dialogs(missing_data_subs)
                
        except Exception as e:
            logger.error(f"Automatic sync failed: {e}")
    
    def on_sync_started(self):
        """Handle sync started signal."""
        logger.info("Subscription sync started")
        # Could show a progress indicator here if desired
    
    def on_sync_completed(self, results: Dict[str, Any]):
        """Handle sync completed signal."""
        logger.info(f"Subscription sync completed: {results}")
        
        # Refresh relevant tabs if they exist
        try:
            if hasattr(self.main_window, 'calendar_tab'):
                self.main_window.calendar_tab.refresh_day()
            if hasattr(self.main_window, 'subscriptions_tab'):
                self.main_window.subscriptions_tab.refresh_from_stripe()
            if hasattr(self.main_window, 'bookings_tab'):
                self.main_window.bookings_tab.refresh_two_weeks()
        except Exception as e:
            logger.error(f"Error refreshing UI after sync: {e}")
    
    def show_schedule_dialogs(self, missing_data_subscriptions: List[Dict[str, Any]]):
        """
        Show schedule completion dialogs for subscriptions missing data.
        
        All dialogs are dismissible and won't get stuck. Users can skip any subscription.
        Fixed to prevent dialog reopening after confirmation.
        
        Args:
            missing_data_subscriptions: List of subscriptions missing schedule data
        """
        try:
            logger.info(f"Showing schedule dialogs for {len(missing_data_subscriptions)} subscriptions")
            
            # Track completed subscriptions to prevent reopening
            completed_subscriptions = set()
            
            # Process each subscription one by one to avoid overwhelming the user
            for i, subscription in enumerate(missing_data_subscriptions, 1):
                subscription_id = subscription.get('id', 'unknown')
                
                # Skip if already completed in this session
                if subscription_id in completed_subscriptions:
                    logger.info(f"Skipping already completed subscription {subscription_id}")
                    continue
                
                try:
                    from subscription_schedule_dialog import SubscriptionScheduleDialog
                    
                    # Create dialog with clear dismissible UI
                    dialog = SubscriptionScheduleDialog(subscription, self.main_window)
                    
                    # Ensure dialog is properly dismissible
                    dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowCloseButtonHint)
                    dialog.setAttribute(Qt.WA_DeleteOnClose, True)  # Auto-cleanup
                    
                    # Connect schedule saved signal with completion tracking
                    def on_schedule_saved_with_tracking(sub_id, schedule_data):
                        completed_subscriptions.add(sub_id)
                        self.on_schedule_saved(sub_id, schedule_data)
                    
                    dialog.schedule_saved.connect(on_schedule_saved_with_tracking)
                    
                    # Show dialog as modal but dismissible
                    dialog.setWindowTitle(f"Complete Schedule ({i}/{len(missing_data_subscriptions)})")
                    result = dialog.exec()  # This blocks until dialog is closed
                    
                    # Mark as completed regardless of result to prevent reopening
                    completed_subscriptions.add(subscription_id)
                    
                    if result == QDialog.Rejected:
                        logger.info(f"User dismissed dialog for subscription {subscription_id}")
                        # Continue with next subscription - user can always skip
                        continue
                    
                except Exception as dialog_error:
                    logger.error(f"Error showing dialog for subscription {subscription_id}: {dialog_error}")
                    # Mark as completed even on error to prevent infinite loops
                    completed_subscriptions.add(subscription_id)
                    # Continue with other subscriptions even if one fails
                    continue
                    
        except Exception as e:
            logger.error(f"Error showing schedule dialogs: {e}")
            # Show user-friendly error that won't get stuck
            try:
                QMessageBox.warning(
                    self.main_window,
                    "Schedule Setup",
                    "Some subscription schedules need to be completed, but there was an error showing the setup dialogs.\n\n" +
                    "Please use the Subscriptions tab to manually complete any missing schedule information."
                )
            except:
                pass  # Don't let error dialogs get stuck either
    
    def on_schedule_saved(self, subscription_id: str, schedule_data: Dict[str, Any]):
        """
        Handle when user saves schedule data for a subscription with enhanced feedback.
        
        Args:
            subscription_id: Stripe subscription ID
            schedule_data: Dictionary with schedule information
        """
        try:
            logger.info(f"Schedule saved for subscription {subscription_id}: {schedule_data}")
            
            # Process the completed schedule
            success = self.auto_sync.handle_schedule_completion(subscription_id, schedule_data, self.main_window)
            
            if success:
                # Get booking count for display
                try:
                    from db import get_conn
                    conn = get_conn()
                    cur = conn.cursor()
                    
                    # Count bookings created for this subscription
                    booking_count = cur.execute("""
                        SELECT COUNT(*) as count FROM bookings 
                        WHERE created_from_sub_id = ? AND source = 'subscription'
                        AND start_dt >= datetime('now')
                    """, (subscription_id,)).fetchone()
                    
                    conn.close()
                    
                    booking_count_text = f"{booking_count['count']} future bookings" if booking_count else "bookings"
                    
                except Exception as e:
                    logger.warning(f"Could not get booking count: {e}")
                    booking_count_text = "bookings"
                
                # Show enhanced success message
                from PySide6.QtWidgets import QMessageBox
                success_msg = (
                    f"✅ Schedule saved successfully for subscription {subscription_id}!\n\n"
                    f"✓ Schedule data saved to local database\n"
                    f"✓ Stripe subscription metadata updated\n"
                    f"✓ Generated {booking_count_text} and calendar entries\n\n"
                    f"Schedule Details:\n"
                    f"• Days: {schedule_data.get('days', 'Not specified')}\n"
                    f"• Time: {schedule_data.get('start_time', '')} - {schedule_data.get('end_time', '')}\n"
                    f"• Location: {schedule_data.get('location', 'Not specified')}\n"
                    f"• Dogs: {schedule_data.get('dogs', 0)}\n"
                    f"• Service: {schedule_data.get('service_code', 'Not specified')}\n\n"
                    f"Your bookings are now available in the Calendar tab."
                )
                
                QMessageBox.information(
                    self.main_window,
                    "Schedule Saved Successfully",
                    success_msg
                )
                
                # Refresh UI components
                self._refresh_ui_after_schedule_save()
                
            else:
                # Show error message - details should have been shown by handle_schedule_completion
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self.main_window,
                    "Schedule Save Error",
                    f"There was an error saving the schedule for subscription {subscription_id}.\n\n"
                    f"Please check the error details that were displayed and try again.\n"
                    f"You can also try completing the schedule manually in the Subscriptions tab."
                )
                
        except Exception as e:
            logger.error(f"Error handling schedule save for {subscription_id}: {e}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self.main_window,
                "Unexpected Error",
                f"An unexpected error occurred while processing the saved schedule:\n\n{str(e)}\n\n"
                f"Please try saving the schedule again or contact support if the problem persists."
            )
    
    def _refresh_ui_after_schedule_save(self):
        """Refresh UI components after successful schedule save."""
        try:
            # Refresh calendar
            if hasattr(self.main_window, 'calendar_tab') and hasattr(self.main_window.calendar_tab, 'refresh_day'):
                self.main_window.calendar_tab.refresh_day()
                logger.debug("Refreshed calendar tab")
            
            # Refresh subscriptions
            if hasattr(self.main_window, 'subscriptions_tab') and hasattr(self.main_window.subscriptions_tab, 'refresh_from_stripe'):
                self.main_window.subscriptions_tab.refresh_from_stripe()
                logger.debug("Refreshed subscriptions tab")
            
            # Refresh bookings
            if hasattr(self.main_window, 'bookings_tab') and hasattr(self.main_window.bookings_tab, 'refresh_two_weeks'):
                self.main_window.bookings_tab.refresh_two_weeks()
                logger.debug("Refreshed bookings tab")
                
        except Exception as e:
            logger.error(f"Error refreshing UI after schedule save: {e}")
            # Don't show error to user for UI refresh issues
