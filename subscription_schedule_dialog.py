"""
Modal popup dialog for collecting missing subscription schedule information.

This dialog is shown when a subscription is missing required schedule data
and prompts the user to fill in the missing details.
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QTimeEdit, QSpinBox, QLineEdit, 
                              QMessageBox, QCheckBox, QFormLayout, QDialogButtonBox, QWidget, QComboBox)
from PySide6.QtCore import Qt, QTime, Signal
from PySide6.QtGui import QFont
import logging

logger = logging.getLogger(__name__)


class DaysPickerWidget(QWidget):
    """Widget for selecting days of the week."""
    
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.checkboxes = []
        
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for day in days:
            checkbox = QCheckBox(day)
            layout.addWidget(checkbox)
            self.checkboxes.append(checkbox)
    
    def set_days(self, days_csv):
        """Set selected days from comma-separated string."""
        selected_days = set((days_csv or "").upper().split(","))
        day_mapping = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, 
                      "FRI": 4, "SAT": 5, "SUN": 6}
        
        for day_code, index in day_mapping.items():
            if index < len(self.checkboxes):
                self.checkboxes[index].setChecked(day_code in selected_days)
    
    def get_days_csv(self):
        """Get selected days as comma-separated string."""
        day_codes = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        selected = []
        
        for i, checkbox in enumerate(self.checkboxes):
            if checkbox.isChecked():
                selected.append(day_codes[i])
        
        return ",".join(selected)


class SubscriptionScheduleDialog(QDialog):
    """Dialog for collecting missing subscription schedule information."""
    
    schedule_saved = Signal(str, dict)  # subscription_id, schedule_data
    
    def __init__(self, subscription_data, parent=None):
        super().__init__(parent)
        self.subscription_data = subscription_data
        self.subscription_id = subscription_data.get("id", "")
        self.missing_fields = subscription_data.get("missing_fields", [])
        self.current_schedule = subscription_data.get("schedule", {})
        
        self.setup_ui()
        self.populate_current_data()
    
    def setup_ui(self):
        """Set up the dialog user interface."""
        self.setWindowTitle("Complete Subscription Schedule")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        # Ensure dialog is always dismissible and doesn't get stuck
        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        
        layout = QVBoxLayout(self)
        
        # Header with subscription info
        header_layout = QVBoxLayout()
        
        title_label = QLabel("Complete Subscription Schedule")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        # Customer information
        customer_info = self._get_customer_display_info()
        info_label = QLabel(f"Subscription: {self.subscription_id}\nCustomer: {customer_info}")
        info_label.setWordWrap(True)
        header_layout.addWidget(info_label)
        
        # Missing fields info
        missing_text = "Please complete the following required information:\n• " + "\n• ".join(self.missing_fields)
        missing_label = QLabel(missing_text)
        missing_label.setStyleSheet("color: #FF6B6B; font-weight: bold;")
        missing_label.setWordWrap(True)
        header_layout.addWidget(missing_label)
        
        layout.addLayout(header_layout)
        
        # Form for schedule data
        form_layout = QFormLayout()
        
        # Days selection
        self.days_widget = DaysPickerWidget()
        form_layout.addRow("Days:", self.days_widget)
        
        # Service selection (if missing)
        if "service_code" in self.missing_fields:
            from service_map import get_all_service_codes, get_service_display_name
            
            self.service_combo = QComboBox()
            self.service_combo.addItem("-- Select Service Type --", "")
            
            service_codes = get_all_service_codes()
            for code in service_codes:
                display_name = get_service_display_name(code)
                self.service_combo.addItem(display_name, code)
            
            form_layout.addRow("Service Type:", self.service_combo)
        else:
            self.service_combo = None
        
        # Time selection
        time_layout = QHBoxLayout()
        self.start_time = QTimeEdit()
        self.start_time.setDisplayFormat("HH:mm")
        self.start_time.setTime(QTime(9, 0))
        time_layout.addWidget(QLabel("Start:"))
        time_layout.addWidget(self.start_time)
        
        time_layout.addWidget(QLabel("End:"))
        self.end_time = QTimeEdit()
        self.end_time.setDisplayFormat("HH:mm") 
        self.end_time.setTime(QTime(10, 0))
        time_layout.addWidget(self.end_time)
        time_layout.addStretch()
        
        form_layout.addRow("Time:", time_layout)
        
        # Location
        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("Service location (e.g., 123 Main St, Brisbane)")
        form_layout.addRow("Location:", self.location_edit)
        
        # Dogs count
        self.dogs_spin = QSpinBox()
        self.dogs_spin.setRange(1, 20)
        self.dogs_spin.setValue(1)
        form_layout.addRow("Number of Dogs:", self.dogs_spin)
        
        # Notes (optional)
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Optional notes")
        form_layout.addRow("Notes:", self.notes_edit)
        
        layout.addLayout(form_layout)
        
        # Buttons with better UX
        button_box = QDialogButtonBox()
        
        self.save_button = QPushButton("Save & Generate Bookings")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self.save_schedule)
        self.save_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }")
        
        skip_button = QPushButton("Skip for Now")
        skip_button.clicked.connect(self.skip_subscription)
        skip_button.setToolTip("You can complete this later in the Subscriptions tab")
        
        button_box.addButton(self.save_button, QDialogButtonBox.AcceptRole)
        button_box.addButton(skip_button, QDialogButtonBox.RejectRole)
        
        layout.addWidget(button_box)
    
    def _get_customer_display_info(self):
        """Get customer display information with robust Stripe API fallback."""
        try:
            from customer_display_helpers import get_robust_customer_display_info
            return get_robust_customer_display_info(self.subscription_data)
        except ImportError:
            # Fallback to local implementation if helper is not available
            logger.warning("customer_display_helpers not available, using fallback")
            return self._get_customer_display_info_fallback()
    
    def _get_customer_display_info_fallback(self):
        """Fallback implementation with improved Stripe API usage."""
        customer = self.subscription_data.get("customer", {})
        
        # Extract initial customer data
        if isinstance(customer, dict):
            name = customer.get("name", "")
            email = customer.get("email", "")
            customer_id = customer.get("id", "")
        else:
            name = getattr(customer, "name", "") if customer else ""
            email = getattr(customer, "email", "") if customer else ""
            customer_id = getattr(customer, "id", "") if customer else ""
        
        # If we have good data, use it
        if name and email:
            return f"{name} ({email})"
        elif name:
            return name
        elif email:
            return email
        
        # Always try to fetch from Stripe if we have customer_id but missing info
        if customer_id:
            try:
                from stripe_integration import _api
                stripe_api = _api()
                logger.info(f"Fetching customer details from Stripe API for {customer_id}")
                customer_obj = stripe_api.Customer.retrieve(customer_id)
                
                fetched_name = getattr(customer_obj, "name", "") or ""
                fetched_email = getattr(customer_obj, "email", "") or ""
                
                if fetched_name and fetched_email:
                    return f"{fetched_name} ({fetched_email})"
                elif fetched_name:
                    return fetched_name
                elif fetched_email:
                    return fetched_email
                else:
                    # Better to show customer ID than "Unknown Customer"
                    return f"Customer {customer_id}"
                    
            except Exception as e:
                logger.warning(f"Failed to fetch customer details from Stripe: {e}")
                # Still better to show customer ID than "Unknown Customer"
                return f"Customer {customer_id}"
        
        return "Unknown Customer"
    
    def populate_current_data(self):
        """Populate form fields with current schedule data if available."""
        if not self.current_schedule:
            return
            
        # Set days
        days_csv = self.current_schedule.get("days", "")
        if days_csv:
            self.days_widget.set_days(days_csv)
        
        # Set times
        start_time = self.current_schedule.get("start_time", "09:00")
        if start_time and start_time != "09:00":
            time_obj = QTime.fromString(start_time, "HH:mm")
            if time_obj.isValid():
                self.start_time.setTime(time_obj)
        
        end_time = self.current_schedule.get("end_time", "10:00")
        if end_time and end_time != "10:00":
            time_obj = QTime.fromString(end_time, "HH:mm")
            if time_obj.isValid():
                self.end_time.setTime(time_obj)
        
        # Set location
        location = self.current_schedule.get("location", "")
        if location:
            self.location_edit.setText(location)
        
        # Set dogs
        dogs = self.current_schedule.get("dogs", 1)
        if dogs > 0:
            self.dogs_spin.setValue(dogs)
        
        # Set notes
        notes = self.current_schedule.get("notes", "")
        if notes:
            self.notes_edit.setText(notes)
    
    def validate_form(self):
        """Validate that all required fields are filled."""
        errors = []
        
        # Validate days
        days_csv = self.days_widget.get_days_csv()
        if not days_csv:
            errors.append("Please select at least one day of the week")
        
        # Validate times
        start = self.start_time.time()
        end = self.end_time.time()
        if start >= end:
            errors.append("End time must be after start time")
        
        # Validate location
        location = self.location_edit.text().strip()
        if not location:
            errors.append("Please enter a service location")
        
        # Dogs is always valid since spinbox enforces range
        
        # Validate service selection (if required)
        if self.service_combo is not None:
            selected_service_code = self.service_combo.currentData()
            if not selected_service_code:
                errors.append("Please select a service type")
        
        return errors
    
    def save_schedule(self):
        """Save the schedule data and emit signal."""
        # Validate form
        errors = self.validate_form()
        if errors:
            error_text = "Please fix the following errors:\n\n• " + "\n• ".join(errors)
            QMessageBox.warning(self, "Validation Error", error_text)
            return
        
        # Collect form data
        schedule_data = {
            "days": self.days_widget.get_days_csv(),
            "start_time": self.start_time.time().toString("HH:mm"),
            "end_time": self.end_time.time().toString("HH:mm"),
            "location": self.location_edit.text().strip(),
            "dogs": self.dogs_spin.value(),
            "notes": self.notes_edit.text().strip()
        }
        
        # Add service code if it was selected
        if self.service_combo is not None:
            selected_service_code = self.service_combo.currentData()
            if selected_service_code:
                schedule_data["service_code"] = selected_service_code
        
        logger.info(f"Saving schedule for subscription {self.subscription_id}: {schedule_data}")
        
        # Emit signal with data
        self.schedule_saved.emit(self.subscription_id, schedule_data)
        
        # Close dialog
        self.accept()
    
    def skip_subscription(self):
        """Handle skipping this subscription for now."""
        logger.info(f"User skipped subscription {self.subscription_id}")
        self.reject()
    
    def closeEvent(self, event):
        """Handle dialog close event to ensure it doesn't get stuck."""
        logger.info(f"Dialog closed for subscription {self.subscription_id}")
        event.accept()  # Always allow closing


def show_subscription_schedule_dialogs(subscriptions_missing_data, parent=None):
    """
    Show schedule completion dialogs for multiple subscriptions.
    
    Args:
        subscriptions_missing_data: List of subscriptions missing schedule data
        parent: Parent widget for the dialogs
        
    Returns:
        List of (subscription_id, schedule_data) tuples for completed schedules
    """
    completed_schedules = []
    
    for subscription in subscriptions_missing_data:
        dialog = SubscriptionScheduleDialog(subscription, parent)
        
        # Connect signal to collect results
        def on_schedule_saved(sub_id, schedule_data):
            completed_schedules.append((sub_id, schedule_data))
        
        dialog.schedule_saved.connect(on_schedule_saved)
        
        # Show dialog and wait for user input
        result = dialog.exec()
        
        # If user cancelled, we still continue with other subscriptions
        if result == QDialog.Rejected:
            logger.info(f"User skipped schedule completion for subscription {subscription.get('id')}")
    
    return completed_schedules


def show_service_selection_dialog(subscription_id, parent=None):
    """
    Show a dialog for user to select service type when mapping fails.
    
    Args:
        subscription_id: Stripe subscription ID
        parent: Parent widget for the dialog
        
    Returns:
        Selected service code or None if cancelled
    """
    from service_map import get_all_service_codes, get_service_display_name
    
    dialog = QDialog(parent)
    dialog.setWindowTitle("Select Service Type")
    dialog.setModal(True)
    dialog.setMinimumWidth(500)
    dialog.setMinimumHeight(400)
    
    # Ensure dialog is dismissible
    dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowCloseButtonHint)
    dialog.setAttribute(Qt.WA_DeleteOnClose, True)
    
    layout = QVBoxLayout(dialog)
    
    # Header info
    header_label = QLabel(f"Service Type Selection Required\n\nSubscription ID: {subscription_id}")
    header_font = QFont()
    header_font.setBold(True)
    header_font.setPointSize(12)
    header_label.setFont(header_font)
    header_label.setWordWrap(True)
    layout.addWidget(header_label)
    
    info_label = QLabel("The service type for this subscription could not be automatically determined. Please select the appropriate service type:")
    info_label.setWordWrap(True)
    layout.addWidget(info_label)
    
    # Service selection
    from PySide6.QtWidgets import QComboBox
    service_combo = QComboBox()
    service_combo.addItem("-- Select Service Type --", "")
    
    service_codes = get_all_service_codes()
    for code in service_codes:
        display_name = get_service_display_name(code)
        service_combo.addItem(display_name, code)
    
    layout.addWidget(service_combo)
    
    # Buttons
    button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    button_box.accepted.connect(dialog.accept)
    button_box.rejected.connect(dialog.reject)
    layout.addWidget(button_box)
    
    # Show dialog and get result
    if dialog.exec() == QDialog.Accepted:
        selected_code = service_combo.currentData()
        if selected_code:
            logger.info(f"User selected service code '{selected_code}' for subscription {subscription_id}")
            return selected_code
        else:
            logger.info(f"User did not select a valid service code for subscription {subscription_id}")
            return None
    else:
        logger.info(f"User cancelled service selection for subscription {subscription_id}")
        return None