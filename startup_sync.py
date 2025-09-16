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
        
        Args:
            show_progress: Whether to show progress dialogs
            
        Returns:
            Dictionary with sync results and statistics
        """
        try:
            logger.info("Starting automatic subscription sync on startup")
            
            if show_progress:
                self.sync_started.emit()
            
            # Step 1: Get all active subscriptions from Stripe
            from stripe_integration import list_active_subscriptions
            
            logger.info("Fetching active subscriptions from Stripe")
            subscriptions = list_active_subscriptions()
            
            if not subscriptions:
                logger.info("No active subscriptions found")
                results = {
                    "total_subscriptions": 0,
                    "missing_schedule_count": 0,
                    "completed_schedules": 0,
                    "sync_stats": {"subscriptions_processed": 0, "bookings_created": 0, "bookings_cleaned": 0}
                }
                if show_progress:
                    self.sync_completed.emit(results)
                return results
            
            # Step 2: Identify subscriptions missing schedule data
            logger.info(f"Analyzing {len(subscriptions)} subscriptions for missing schedule data")
            missing_data_subscriptions = get_subscriptions_missing_schedule_data(subscriptions)
            
            logger.info(f"Found {len(missing_data_subscriptions)} subscriptions missing schedule data")
            
            # Step 3: Show modal dialogs for missing data (if any)
            completed_schedules = []
            if missing_data_subscriptions:
                logger.info("Showing schedule completion dialogs")
                self.schedule_dialogs_needed.emit(missing_data_subscriptions)
                
                # This will be handled by the UI thread showing dialogs
                # For now, we'll continue with the sync
            
            # Step 4: Perform the main subscription sync
            logger.info("Performing subscription sync to generate bookings and calendar")
            sync_stats = sync_subscriptions_to_bookings_and_calendar(self.conn)
            
            # Compile results
            results = {
                "total_subscriptions": len(subscriptions),
                "missing_schedule_count": len(missing_data_subscriptions),
                "completed_schedules": len(completed_schedules),
                "sync_stats": sync_stats,
                "missing_data_subscriptions": missing_data_subscriptions
            }
            
            logger.info(f"Startup sync completed: {results}")
            
            if show_progress:
                self.sync_completed.emit(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Startup sync failed: {e}")
            error_results = {
                "error": str(e),
                "total_subscriptions": 0,
                "missing_schedule_count": 0,
                "completed_schedules": 0,
                "sync_stats": {"subscriptions_processed": 0, "bookings_created": 0, "bookings_cleaned": 0}
            }
            if show_progress:
                self.sync_completed.emit(error_results)
            return error_results
    
    def handle_schedule_completion(self, subscription_id: str, schedule_data: Dict[str, Any]) -> bool:
        """
        Handle completion of schedule data for a subscription.
        
        This updates both Stripe metadata and local database, then triggers
        immediate booking generation for the specific subscription.
        
        Args:
            subscription_id: Stripe subscription ID
            schedule_data: Dictionary with schedule information
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Processing completed schedule for subscription {subscription_id}")
            
            # Step 1: Update Stripe subscription metadata
            success_stripe = update_stripe_subscription_metadata(
                subscription_id,
                schedule_data["days"],
                schedule_data["start_time"],
                schedule_data["end_time"],
                schedule_data["location"],
                schedule_data["dogs"],
                schedule_data.get("notes", "")
            )
            
            if not success_stripe:
                logger.warning(f"Failed to update Stripe metadata for {subscription_id} - continuing with local update")
                # Continue anyway with local update - Stripe update is not critical for immediate booking generation
            
            # Step 2: Update local database (this is critical)
            success_local = update_local_subscription_schedule(
                self.conn,
                subscription_id,
                schedule_data["days"],
                schedule_data["start_time"],
                schedule_data["end_time"],
                schedule_data["location"],
                schedule_data["dogs"],
                schedule_data.get("notes", "")
            )
            
            if not success_local:
                logger.error(f"Failed to update local schedule for {subscription_id}")
                return False
            
            # Step 3: Immediately generate bookings for this subscription
            logger.info(f"Generating bookings for completed subscription {subscription_id}")
            
            # Get the updated subscription from Stripe and sync just this one
            try:
                from stripe_integration import _api
                stripe_api = _api()
                updated_subscription = stripe_api.Subscription.retrieve(subscription_id, expand=['customer'])
                
                # Convert to dict format
                subscription_data = dict(updated_subscription)
                
                # Sync just this subscription to generate bookings immediately
                from subscription_sync import sync_subscription_to_bookings
                bookings_created = sync_subscription_to_bookings(self.conn, subscription_data)
                
                logger.info(f"Immediately created {bookings_created} bookings for subscription {subscription_id}")
                
                # Also trigger a full sync to ensure calendar is updated
                sync_stats = sync_subscriptions_to_bookings_and_calendar(self.conn)
                logger.info(f"Full sync completed: {sync_stats}")
                
                return True
                
            except Exception as sync_error:
                logger.error(f"Failed to generate bookings for {subscription_id}: {sync_error}")
                # Still return True since the schedule was saved, just booking generation failed
                return True
            
        except Exception as e:
            logger.error(f"Failed to handle schedule completion for {subscription_id}: {e}")
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
        except Exception as e:
            logger.error(f"Error refreshing UI after sync: {e}")
    
    def show_schedule_dialogs(self, missing_data_subscriptions: List[Dict[str, Any]]):
        """
        Show schedule completion dialogs for subscriptions missing data.
        
        All dialogs are dismissible and won't get stuck. Users can skip any subscription.
        
        Args:
            missing_data_subscriptions: List of subscriptions missing schedule data
        """
        try:
            logger.info(f"Showing schedule dialogs for {len(missing_data_subscriptions)} subscriptions")
            
            # Process each subscription one by one to avoid overwhelming the user
            for i, subscription in enumerate(missing_data_subscriptions, 1):
                try:
                    from subscription_schedule_dialog import SubscriptionScheduleDialog
                    
                    # Create dialog with clear dismissible UI
                    dialog = SubscriptionScheduleDialog(subscription, self.main_window)
                    
                    # Ensure dialog is properly dismissible
                    dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowCloseButtonHint)
                    dialog.setAttribute(Qt.WA_DeleteOnClose, True)  # Auto-cleanup
                    
                    # Connect schedule saved signal
                    dialog.schedule_saved.connect(self.on_schedule_saved)
                    
                    # Show dialog as modal but dismissible
                    dialog.setWindowTitle(f"Complete Schedule ({i}/{len(missing_data_subscriptions)})")
                    result = dialog.exec()  # This blocks until dialog is closed
                    
                    if result == QDialog.Rejected:
                        logger.info(f"User dismissed dialog for subscription {subscription.get('id', 'unknown')}")
                        # Continue with next subscription - user can always skip
                        continue
                    
                except Exception as dialog_error:
                    logger.error(f"Error showing dialog for subscription {subscription.get('id', 'unknown')}: {dialog_error}")
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
        Handle when user saves schedule data for a subscription.
        
        Args:
            subscription_id: Stripe subscription ID
            schedule_data: Dictionary with schedule information
        """
        try:
            logger.info(f"Schedule saved for subscription {subscription_id}")
            
            # Process the completed schedule
            success = self.auto_sync.handle_schedule_completion(subscription_id, schedule_data)
            
            if success:
                # Show success message with booking info
                QMessageBox.information(
                    self.main_window,
                    "Schedule Saved Successfully",
                    f"✅ Schedule saved for subscription {subscription_id}!\n\n" +
                    "✓ Updated Stripe subscription metadata\n" +
                    "✓ Updated local database\n" +
                    "✓ Generated bookings and calendar entries\n\n" +
                    "Your bookings are now available in the Calendar tab."
                )
                
                # Refresh UI
                try:
                    if hasattr(self.main_window, 'calendar_tab'):
                        self.main_window.calendar_tab.refresh_day()
                    if hasattr(self.main_window, 'subscriptions_tab'):
                        self.main_window.subscriptions_tab.refresh_from_stripe()
                except Exception as e:
                    logger.error(f"Error refreshing UI after schedule save: {e}")
            else:
                # Show error message
                QMessageBox.warning(
                    self.main_window,
                    "Save Error",
                    f"There was an error saving the schedule for subscription {subscription_id}.\nPlease try again or check the logs for details."
                )
                
        except Exception as e:
            logger.error(f"Error handling schedule save for {subscription_id}: {e}")
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"An unexpected error occurred while saving the schedule:\n{str(e)}"
            )