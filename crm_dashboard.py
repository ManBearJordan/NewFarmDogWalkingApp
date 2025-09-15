# crm_dashboard.py
"""
CRM Dashboard Tab for the Dog Walking App
Provides visual interface for customer relationship management features
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel, 
    QTableWidget, QTableWidgetItem, QPushButton, QComboBox, QLineEdit,
    QTextEdit, QDateEdit, QListWidget, QListWidgetItem, QDialog, QFormLayout,
    QColorDialog, QMessageBox, QTabWidget, QCheckBox, QSpinBox
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QColor, QPalette, QFont
from datetime import datetime, timedelta
from typing import List

from crm_module import CRMManager, InteractionType, CustomerStatus, CustomerTag
from db import get_conn

class AddInteractionDialog(QDialog):
    def __init__(self, client_id: int, client_name: str, parent=None):
        super().__init__(parent)
        self.client_id = client_id
        self.setWindowTitle(f"Add Interaction - {client_name}")
        self.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # Form layout
        form = QFormLayout()
        
        self.interaction_type = QComboBox()
        for interaction_type in InteractionType:
            self.interaction_type.addItem(interaction_type.value.replace("_", " ").title(), interaction_type)
        
        self.subject = QLineEdit()
        self.description = QTextEdit()
        self.description.setMaximumHeight(100)
        
        self.follow_up_date = QDateEdit()
        self.follow_up_date.setCalendarPopup(True)
        self.follow_up_date.setDate(QDate.currentDate().addDays(7))
        
        self.needs_follow_up = QCheckBox("Needs follow-up")
        self.needs_follow_up.toggled.connect(self.follow_up_date.setEnabled)
        self.follow_up_date.setEnabled(False)
        
        form.addRow("Type:", self.interaction_type)
        form.addRow("Subject:", self.subject)
        form.addRow("Description:", self.description)
        form.addRow("", self.needs_follow_up)
        form.addRow("Follow-up Date:", self.follow_up_date)
        
        layout.addLayout(form)
        
        # Buttons
        buttons = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)
    
    def get_interaction_data(self):
        return {
            "interaction_type": self.interaction_type.currentData(),
            "subject": self.subject.text(),
            "description": self.description.toPlainText(),
            "follow_up_date": self.follow_up_date.date().toString("yyyy-MM-dd") if self.needs_follow_up.isChecked() else None
        }

class CustomerTagsWidget(QWidget):
    tags_changed = Signal()
    
    def __init__(self, client_id: int, crm_manager: CRMManager, parent=None):
        super().__init__(parent)
        self.client_id = client_id
        self.crm = crm_manager
        
        layout = QVBoxLayout(self)
        
        # Available tags
        self.available_tags = QComboBox()
        self.refresh_available_tags()
        
        add_tag_btn = QPushButton("Add Tag")
        add_tag_btn.clicked.connect(self.add_tag)
        
        tag_controls = QHBoxLayout()
        tag_controls.addWidget(QLabel("Add Tag:"))
        tag_controls.addWidget(self.available_tags)
        tag_controls.addWidget(add_tag_btn)
        tag_controls.addStretch()
        
        layout.addLayout(tag_controls)
        
        # Current tags
        self.current_tags_list = QListWidget()
        self.current_tags_list.itemDoubleClicked.connect(self.remove_tag)
        layout.addWidget(QLabel("Current Tags (double-click to remove):"))
        layout.addWidget(self.current_tags_list)
        
        self.refresh_current_tags()
    
    def refresh_available_tags(self):
        self.available_tags.clear()
        for tag in self.crm.get_all_tags():
            self.available_tags.addItem(tag.name, tag.id)
    
    def refresh_current_tags(self):
        self.current_tags_list.clear()
        for tag in self.crm.get_client_tags(self.client_id):
            item = QListWidgetItem(tag.name)
            item.setData(Qt.UserRole, tag.id)
            item.setBackground(QColor(tag.color).lighter(150))
            self.current_tags_list.addItem(item)
    
    def add_tag(self):
        tag_id = self.available_tags.currentData()
        if tag_id and self.crm.add_tag_to_client(self.client_id, tag_id):
            self.refresh_current_tags()
            self.tags_changed.emit()
    
    def remove_tag(self, item):
        tag_id = item.data(Qt.UserRole)
        if tag_id and self.crm.remove_tag_from_client(self.client_id, tag_id):
            self.refresh_current_tags()
            self.tags_changed.emit()

class CRMDashboardTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.conn = get_conn()
        self.crm = CRMManager(self.conn)
        
        # Update customer statistics on startup
        try:
            self.crm.bulk_update_customer_stats()
        except Exception as e:
            print(f"Error updating customer stats: {e}")
        
        self.setup_ui()
        self.refresh_all_data()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create tab widget for different CRM views
        self.tab_widget = QTabWidget()
        
        # Dashboard Overview
        self.setup_dashboard_tab()
        
        # Customer Analytics
        self.setup_analytics_tab()
        
        # Communication Center
        self.setup_communication_tab()
        
        # Customer Management
        self.setup_management_tab()
        
        layout.addWidget(self.tab_widget)
    
    def setup_dashboard_tab(self):
        dashboard_widget = QWidget()
        layout = QGridLayout(dashboard_widget)
        
        # Key Metrics Cards
        self.setup_metrics_cards(layout)
        
        # Quick Actions
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QHBoxLayout(actions_group)
        
        add_interaction_btn = QPushButton("Add Customer Interaction")
        add_interaction_btn.clicked.connect(self.show_add_interaction_dialog)
        
        bulk_update_btn = QPushButton("Update Customer Stats")
        bulk_update_btn.clicked.connect(self.bulk_update_stats)
        
        actions_layout.addWidget(add_interaction_btn)
        actions_layout.addWidget(bulk_update_btn)
        actions_layout.addStretch()
        
        layout.addWidget(actions_group, 1, 0, 1, 2)
        
        # Recent Activity
        activity_group = QGroupBox("Recent Customer Activity")
        activity_layout = QVBoxLayout(activity_group)
        
        self.recent_activity_table = QTableWidget()
        self.recent_activity_table.setColumnCount(4)
        self.recent_activity_table.setHorizontalHeaderLabels(["Date", "Customer", "Type", "Subject"])
        activity_layout.addWidget(self.recent_activity_table)
        
        layout.addWidget(activity_group, 2, 0, 1, 2)
        
        self.tab_widget.addTab(dashboard_widget, "Dashboard")
    
    def setup_metrics_cards(self, layout):
        # Total Customers
        self.total_customers_label = QLabel("0")
        self.total_customers_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #007bff;")
        customers_card = self.create_metric_card("Total Customers", self.total_customers_label)
        layout.addWidget(customers_card, 0, 0)
        
        # Active Customers
        self.active_customers_label = QLabel("0")
        self.active_customers_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #28a745;")
        active_card = self.create_metric_card("Active Customers", self.active_customers_label)
        layout.addWidget(active_card, 0, 1)
        
        # At Risk Customers
        self.at_risk_label = QLabel("0")
        self.at_risk_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #dc3545;")
        at_risk_card = self.create_metric_card("At Risk Customers", self.at_risk_label)
        layout.addWidget(at_risk_card, 0, 2)
        
        # Follow-ups Needed
        self.follow_ups_label = QLabel("0")
        self.follow_ups_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #fd7e14;")
        follow_ups_card = self.create_metric_card("Follow-ups Needed", self.follow_ups_label)
        layout.addWidget(follow_ups_card, 0, 3)
    
    def create_metric_card(self, title: str, value_label: QLabel) -> QGroupBox:
        card = QGroupBox(title)
        layout = QVBoxLayout(card)
        layout.addWidget(value_label)
        return card
    
    def setup_analytics_tab(self):
        analytics_widget = QWidget()
        layout = QVBoxLayout(analytics_widget)
        
        # High Value Customers
        high_value_group = QGroupBox("High Value Customers (>$500 lifetime)")
        high_value_layout = QVBoxLayout(high_value_group)
        
        self.high_value_table = QTableWidget()
        self.high_value_table.setColumnCount(3)
        self.high_value_table.setHorizontalHeaderLabels(["Customer", "Total Revenue", "Actions"])
        high_value_layout.addWidget(self.high_value_table)
        
        layout.addWidget(high_value_group)
        
        # Customer Segments
        segments_group = QGroupBox("Customer Segments")
        segments_layout = QVBoxLayout(segments_group)
        
        self.segments_table = QTableWidget()
        self.segments_table.setColumnCount(3)
        self.segments_table.setHorizontalHeaderLabels(["Tag", "Customer Count", "Avg Revenue"])
        segments_layout.addWidget(self.segments_table)
        
        layout.addWidget(segments_group)
        
        self.tab_widget.addTab(analytics_widget, "Analytics")
    
    def setup_communication_tab(self):
        comm_widget = QWidget()
        layout = QVBoxLayout(comm_widget)
        
        # Follow-ups Needed
        follow_ups_group = QGroupBox("Customers Needing Follow-up")
        follow_ups_layout = QVBoxLayout(follow_ups_group)
        
        self.follow_ups_table = QTableWidget()
        self.follow_ups_table.setColumnCount(3)
        self.follow_ups_table.setHorizontalHeaderLabels(["Customer", "Email", "Actions"])
        follow_ups_layout.addWidget(self.follow_ups_table)
        
        layout.addWidget(follow_ups_group)
        
        # At Risk Customers
        at_risk_group = QGroupBox("At Risk Customers (No bookings in 60+ days)")
        at_risk_layout = QVBoxLayout(at_risk_group)
        
        self.at_risk_table = QTableWidget()
        self.at_risk_table.setColumnCount(3)
        self.at_risk_table.setHorizontalHeaderLabels(["Customer", "Last Booking", "Actions"])
        at_risk_layout.addWidget(self.at_risk_table)
        
        layout.addWidget(at_risk_group)
        
        self.tab_widget.addTab(comm_widget, "Communication")
    
    def setup_management_tab(self):
        mgmt_widget = QWidget()
        layout = QVBoxLayout(mgmt_widget)
        
        # Customer Status Management
        status_group = QGroupBox("Customer Status Management")
        status_layout = QVBoxLayout(status_group)
        
        # Customer selector
        customer_selector = QHBoxLayout()
        self.customer_combo = QComboBox()
        self.load_customers()
        self.customer_combo.currentTextChanged.connect(self.on_customer_selected)
        
        customer_selector.addWidget(QLabel("Select Customer:"))
        customer_selector.addWidget(self.customer_combo)
        customer_selector.addStretch()
        
        status_layout.addLayout(customer_selector)
        
        # Customer details and management
        self.customer_details_widget = QWidget()
        self.setup_customer_details_widget()
        status_layout.addWidget(self.customer_details_widget)
        
        layout.addWidget(status_group)
        
        self.tab_widget.addTab(mgmt_widget, "Customer Management")
    
    def setup_customer_details_widget(self):
        layout = QGridLayout(self.customer_details_widget)
        
        # Customer status
        self.status_combo = QComboBox()
        for status in CustomerStatus:
            self.status_combo.addItem(status.value.replace("_", " ").title(), status)
        self.status_combo.currentTextChanged.connect(self.update_customer_status)
        
        layout.addWidget(QLabel("Status:"), 0, 0)
        layout.addWidget(self.status_combo, 0, 1)
        
        # Customer tags
        self.tags_widget = CustomerTagsWidget(0, self.crm)  # Will be updated when customer selected
        layout.addWidget(QLabel("Tags:"), 1, 0, Qt.AlignTop)
        layout.addWidget(self.tags_widget, 1, 1)
        
        # Interaction history
        self.interactions_table = QTableWidget()
        self.interactions_table.setColumnCount(4)
        self.interactions_table.setHorizontalHeaderLabels(["Date", "Type", "Subject", "Follow-up"])
        layout.addWidget(QLabel("Recent Interactions:"), 2, 0, Qt.AlignTop)
        layout.addWidget(self.interactions_table, 2, 1)
        
        # Add interaction button
        add_interaction_btn = QPushButton("Add Interaction")
        add_interaction_btn.clicked.connect(self.add_interaction_for_selected_customer)
        layout.addWidget(add_interaction_btn, 3, 1)
    
    def load_customers(self):
        self.customer_combo.clear()
        self.customer_combo.addItem("Select a customer...", None)
        
        cur = self.conn.cursor()
        cur.execute("SELECT id, name FROM clients ORDER BY name")
        for row in cur.fetchall():
            self.customer_combo.addItem(row["name"], row["id"])
    
    def on_customer_selected(self):
        client_id = self.customer_combo.currentData()
        if client_id:
            self.load_customer_details(client_id)
    
    def load_customer_details(self, client_id: int):
        # Update tags widget
        self.tags_widget.client_id = client_id
        self.tags_widget.refresh_current_tags()
        
        # Load customer status
        cur = self.conn.cursor()
        client_row = cur.execute("SELECT status FROM clients WHERE id = ?", (client_id,)).fetchone()
        if client_row and client_row["status"]:
            status = client_row["status"]
            for i in range(self.status_combo.count()):
                if self.status_combo.itemData(i).value == status:
                    self.status_combo.setCurrentIndex(i)
                    break
        
        # Load interactions
        interactions = self.crm.get_client_interactions(client_id, limit=20)
        self.interactions_table.setRowCount(len(interactions))
        
        for row, interaction in enumerate(interactions):
            self.interactions_table.setItem(row, 0, QTableWidgetItem(
                interaction.interaction_date[:10]  # Show date only
            ))
            self.interactions_table.setItem(row, 1, QTableWidgetItem(
                interaction.interaction_type.value.replace("_", " ").title()
            ))
            self.interactions_table.setItem(row, 2, QTableWidgetItem(interaction.subject))
            self.interactions_table.setItem(row, 3, QTableWidgetItem(
                interaction.follow_up_date[:10] if interaction.follow_up_date else ""
            ))
    
    def update_customer_status(self):
        client_id = self.customer_combo.currentData()
        if client_id:
            status = self.status_combo.currentData()
            self.crm.update_client_status(client_id, status)
            self.refresh_metrics()
    
    def add_interaction_for_selected_customer(self):
        client_id = self.customer_combo.currentData()
        client_name = self.customer_combo.currentText()
        
        if client_id and client_name != "Select a customer...":
            self.show_add_interaction_dialog(client_id, client_name)
    
    def show_add_interaction_dialog(self, client_id=None, client_name=None):
        if not client_id:
            # Show customer selection dialog first
            cur = self.conn.cursor()
            cur.execute("SELECT id, name FROM clients ORDER BY name")
            customers = cur.fetchall()
            
            if not customers:
                QMessageBox.information(self, "No Customers", "No customers found. Add customers first.")
                return
            
            # For now, just take the first customer as an example
            # In a full implementation, you'd show a selection dialog
            client_id = customers[0]["id"]
            client_name = customers[0]["name"]
        
        dialog = AddInteractionDialog(client_id, client_name, self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_interaction_data()
            self.crm.add_interaction(
                client_id=client_id,
                interaction_type=data["interaction_type"],
                subject=data["subject"],
                description=data["description"],
                follow_up_date=data["follow_up_date"]
            )
            self.refresh_all_data()
            self.load_customer_details(client_id)  # Refresh customer details if showing
    
    def bulk_update_stats(self):
        self.crm.bulk_update_customer_stats()
        self.refresh_all_data()
        QMessageBox.information(self, "Update Complete", "Customer statistics updated successfully.")
    
    def refresh_all_data(self):
        self.refresh_metrics()
        self.refresh_recent_activity()
        self.refresh_high_value_customers()
        self.refresh_follow_ups()
        self.refresh_at_risk_customers()
    
    def refresh_metrics(self):
        cur = self.conn.cursor()
        
        # Total customers
        total = cur.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        self.total_customers_label.setText(str(total))
        
        # Active customers
        active = cur.execute("SELECT COUNT(*) FROM clients WHERE status = 'active'").fetchone()[0]
        self.active_customers_label.setText(str(active))
        
        # At risk customers
        at_risk = len(self.crm.get_at_risk_customers())
        self.at_risk_label.setText(str(at_risk))
        
        # Follow-ups needed
        follow_ups = len(self.crm.get_clients_needing_follow_up())
        self.follow_ups_label.setText(str(follow_ups))
    
    def refresh_recent_activity(self):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT ci.interaction_date, c.name, ci.interaction_type, ci.subject
            FROM customer_interactions ci
            JOIN clients c ON ci.client_id = c.id
            ORDER BY ci.interaction_date DESC
            LIMIT 10
        """)
        
        rows = cur.fetchall()
        self.recent_activity_table.setRowCount(len(rows))
        
        for row_idx, row in enumerate(rows):
            self.recent_activity_table.setItem(row_idx, 0, QTableWidgetItem(row["interaction_date"][:10]))
            self.recent_activity_table.setItem(row_idx, 1, QTableWidgetItem(row["name"]))
            self.recent_activity_table.setItem(row_idx, 2, QTableWidgetItem(
                row["interaction_type"].replace("_", " ").title()
            ))
            self.recent_activity_table.setItem(row_idx, 3, QTableWidgetItem(row["subject"]))
    
    def refresh_high_value_customers(self):
        high_value = self.crm.get_high_value_customers(min_revenue_cents=50000)  # $500+
        self.high_value_table.setRowCount(len(high_value))
        
        for row_idx, (client_id, name, revenue) in enumerate(high_value):
            self.high_value_table.setItem(row_idx, 0, QTableWidgetItem(name))
            self.high_value_table.setItem(row_idx, 1, QTableWidgetItem(f"${revenue/100:.2f}"))
            
            actions_btn = QPushButton("View Details")
            actions_btn.clicked.connect(lambda checked, cid=client_id: self.show_customer_details(cid))
            self.high_value_table.setCellWidget(row_idx, 2, actions_btn)
    
    def refresh_follow_ups(self):
        follow_ups = self.crm.get_clients_needing_follow_up()
        self.follow_ups_table.setRowCount(len(follow_ups))
        
        for row_idx, (client_id, name, email) in enumerate(follow_ups):
            self.follow_ups_table.setItem(row_idx, 0, QTableWidgetItem(name))
            self.follow_ups_table.setItem(row_idx, 1, QTableWidgetItem(email or ""))
            
            actions_btn = QPushButton("Add Interaction")
            actions_btn.clicked.connect(lambda checked, cid=client_id, cname=name: 
                                      self.show_add_interaction_dialog(cid, cname))
            self.follow_ups_table.setCellWidget(row_idx, 2, actions_btn)
    
    def refresh_at_risk_customers(self):
        at_risk = self.crm.get_at_risk_customers()
        self.at_risk_table.setRowCount(len(at_risk))
        
        for row_idx, (client_id, name, last_booking) in enumerate(at_risk):
            self.at_risk_table.setItem(row_idx, 0, QTableWidgetItem(name))
            self.at_risk_table.setItem(row_idx, 1, QTableWidgetItem(last_booking[:10] if last_booking else "Never"))
            
            actions_btn = QPushButton("Contact Customer")
            actions_btn.clicked.connect(lambda checked, cid=client_id, cname=name: 
                                      self.show_add_interaction_dialog(cid, cname))
            self.at_risk_table.setCellWidget(row_idx, 2, actions_btn)
    
    def show_customer_details(self, client_id: int):
        # Switch to management tab and select the customer
        self.tab_widget.setCurrentIndex(3)  # Management tab
        
        # Find and select the customer in the combo box
        for i in range(self.customer_combo.count()):
            if self.customer_combo.itemData(i) == client_id:
                self.customer_combo.setCurrentIndex(i)
                break