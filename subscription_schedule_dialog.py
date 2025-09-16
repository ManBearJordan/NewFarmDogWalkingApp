"""
Modal popup dialog for collecting missing subscription schedule information.

This dialog is shown when a subscription is missing required schedule data
and prompts the user to fill in the missing details.
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QTimeEdit, QSpinBox, QLineEdit, 
                              QMessageBox, QCheckBox, QFormLayout, QDialogButtonBox)
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
        """Get customer display information from subscription data."""
        customer = self.subscription_data.get("customer", {})
        if isinstance(customer, dict):
            name = customer.get("name", "")
            email = customer.get("email", "")
        else:
            name = getattr(customer, "name", "") if customer else ""
            email = getattr(customer, "email", "") if customer else ""
        
        if name and email:
            return f"{name} ({email})"
        elif name:
            return name
        elif email:
            return email
        else:
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