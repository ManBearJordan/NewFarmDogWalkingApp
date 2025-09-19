from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PySide6 import QtCore, QtGui, QtWidgets
import os, sys, json
import logging
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QTabWidget, QDateTimeEdit, QComboBox, QFileDialog, QSpinBox, QDateEdit, QTimeEdit, QCheckBox, QDialog, QMenu, QGroupBox, QHeaderView)
from PySide6.QtCore import Qt, QDateTime, QTimer, Signal, QDate, QTime, QThread, QObject
from PySide6.QtGui import QDesktopServices, QAction, QCursor, QBrush, QColor
from PySide6.QtCore import QUrl
from datetime import datetime, timezone, timedelta, time
from collections import defaultdict
import subprocess
import threading
import urllib.request
import urllib.error

from db import init_db, get_conn, backup_db, clear_future_sub_occurrences, materialize_sub_occurrences, add_booking, booking_items_total_cents, add_or_upsert_booking, set_booking_invoice, get_client_credit, add_client_credit, use_client_credit
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
BRISBANE = ZoneInfo("Australia/Brisbane")
from ics_export import export_bookings
from stripe_integration import (
    list_products, list_recent_invoices, list_subscriptions, open_url,
    ensure_customer, create_invoice_with_item, list_two_week_invoices,
    list_booking_services, create_draft_invoice_for_booking,
    _create_invoice_and_open, _open_invoice_in_dashboard, open_invoice_smart
)
import bookings_two_week as btw
from reports_tab import ReportsTab
from date_range_helpers import resolve_range
from crm_dashboard import CRMDashboardTab

# Initialize logger
logger = logging.getLogger(__name__)

# --- Helpers for Calendar view ---------------------------------------------

def get_client_bundle(conn, client_id: int, fallback_addr: str = "") -> tuple[str, str, str]:
    """
    Returns (client_name, address, pets_csv) for a given client_id.
    Falls back to booking/sub address if client has no address saved.
    """
    name, addr = "", ""
    try:
        row = conn.execute(
            "SELECT name, address FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
        if row:
            name = row["name"] or ""
            addr = (row["address"] or "").strip()
    except Exception:
        pass

    if not addr:
        addr = (fallback_addr or "").strip()

    # Collect pet names
    pets = []
    try:
        for p in conn.execute(
            "SELECT name FROM pets WHERE client_id = ? ORDER BY name", (client_id,)
        ).fetchall():
            if p and p["name"]:
                pets.append(p["name"])
    except Exception:
        pass

    return (name, addr, ", ".join(pets))


def friendly_service_label(service_code: str | None, default_label: str = "") -> str:
    """
    Convert a service_code (e.g. WALK_SHORT_SINGLE) or a raw code into
    a nice label. Uses the central service mapping.
    """
    from service_map import get_service_display_name
    
    return get_service_display_name(service_code, default_label)


# put this right above ts_to_iso (or inside the function)
import datetime as _dt

def ts_to_iso(ts: int) -> str:
    return _dt.datetime.fromtimestamp(int(ts), tz=_dt.timezone.utc)\
                       .strftime("%Y-%m-%dT%H:%M:%S")

# helpers
def _qdt_to_iso(qdt) -> str:
    # Store as local time ISO; change format if you need seconds with 'T'
    return qdt.toString("yyyy-MM-dd HH:mm:ss")


def _service_label_from_row(row: dict) -> str:
    """
    Returns a human label for the service.
    Works for manual bookings, subscription holds, or invoice-derived rows.
    Priority:
      service_label -> meta.service_name -> meta.service_code -> product_name -> price_nickname -> "Service"
    """
    # explicit labels you already save
    lbl = row.get("service_label") or row.get("service")
    # if someone stored "Subscription" as a placeholder, ignore it
    if isinstance(lbl, str) and lbl.strip().lower() == "subscription":
        lbl = None

    meta = row.get("meta") or row.get("metadata") or {}
    if not lbl:
        lbl = meta.get("service_name")
    if not lbl:
        code = meta.get("service_code")
        if code:
            lbl = code.replace("_", " ").title()

    if not lbl:
        # common fallbacks you may have on rows
        lbl = row.get("product_name") or row.get("price_nickname")

    return lbl or "Service"


class DaysPicker(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self); lay.setContentsMargins(0,0,0,0)
        self.btns = []
        for name in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]:
            b = QCheckBox(name); lay.addWidget(b); self.btns.append(b)

    def set_days(self, csv):
        s = set((csv or "").upper().split(","))
        mapd = {"MON":"Mon","TUE":"Tue","WED":"Wed","THU":"Thu","FRI":"Fri","SAT":"Sat","SUN":"Sun"}
        for b in self.btns:
            b.setChecked(b.text() in [mapd.get(d,d).title() for d in s])

    def get_days_csv(self):
        pick = []
        order = [("Mon","MON"),("Tue","TUE"),("Wed","WED"),("Thu","THU"),("Fri","FRI"),("Sat","SAT"),("Sun","SUN")]
        for label, code in order:
            for b in self.btns:
                if b.text()==label and b.isChecked():
                    pick.append(code)
        return ",".join(pick)

# ---------------- Clients Tab ----------------
class ClientsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.conn = get_conn()
        layout = QVBoxLayout(self)

        # Create form widgets
        form = QHBoxLayout()
        self.name = QLineEdit()
        self.email = QLineEdit()
        self.phone = QLineEdit()
        self.addr = QLineEdit()
        self.notes = QLineEdit()
        add_btn = QPushButton("Add/Update Client")
        add_btn.clicked.connect(self.add_client)
        
        form.addWidget(QLabel("Name:"))
        form.addWidget(self.name)
        form.addWidget(QLabel("Email:"))
        form.addWidget(self.email)
        form.addWidget(QLabel("Phone:"))
        form.addWidget(self.phone)
        form.addWidget(QLabel("Address:"))
        form.addWidget(self.addr)
        form.addWidget(QLabel("Notes:"))
        form.addWidget(self.notes)
        form.addWidget(add_btn)
        layout.addLayout(form)

        tools = QHBoxLayout()
        sync_btn = QPushButton("Sync Stripe customers"); sync_btn.clicked.connect(self.sync_customers)
        link_btn = QPushButton("Link selected to Stripe customer…"); link_btn.clicked.connect(self.link_selected_to_customer)
        open_cust_btn = QPushButton("Open in Stripe (selected)"); open_cust_btn.clicked.connect(self.open_selected_in_stripe)
        tools.addWidget(sync_btn); tools.addWidget(link_btn); tools.addWidget(open_cust_btn)
        layout.addLayout(tools)

        # Credit management row
        credit_row = QHBoxLayout()
        self.lbl_credit = QLabel("Credit: $0.00")
        self.add_credit_btn = QPushButton("Add credit")
        self.add_credit_btn.clicked.connect(self.on_add_credit_clicked)
        credit_row.addWidget(self.lbl_credit)
        credit_row.addWidget(self.add_credit_btn)
        credit_row.addStretch()
        layout.addLayout(credit_row)

        self.table = QTableWidget(0,10)
        self.table.setHorizontalHeaderLabels(["ID","Name","Email","Phone","Address","Notes","Credit","Status","Tags","StripeCustomerID"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemSelectionChanged.connect(self.on_row_select)
        layout.addWidget(self.table)

        del_btn = QPushButton("Delete selected"); del_btn.clicked.connect(self.delete_client)
        layout.addWidget(del_btn)

        self.refresh()
        
        # Auto-sync customers on load (non-blocking)
        # Commented out to prevent startup hang - user can manually sync if needed
        # try:
        #     self.sync_customers(show_message=False)
        # except Exception:
        #     # If auto-sync fails, continue without showing error to user
        #     pass

    def refresh(self):
        from crm_module import CRMManager
        crm = CRMManager(self.conn)
        
        rows = self.conn.execute("SELECT id,name,email,phone,address,notes,COALESCE(credit_cents,0) as credit_cents,status,stripe_customer_id FROM clients ORDER BY id DESC").fetchall()
        self.table.setRowCount(0)
        for r in rows:
            row = self.table.rowCount(); self.table.insertRow(row)
            for i,k in enumerate(["id","name","email","phone","address","notes"]):
                self.table.setItem(row,i,QTableWidgetItem(str(r[k] or "")))
            # Format credit as dollars
            credit_cents = r["credit_cents"] or 0
            credit_display = f"${credit_cents/100:.2f}"
            self.table.setItem(row,6,QTableWidgetItem(credit_display))
            
            # Show customer status
            status = r["status"] or "active"
            self.table.setItem(row,7,QTableWidgetItem(status.title()))
            
            # Show customer tags
            client_tags = crm.get_client_tags(r["id"])
            tag_names = [tag.name for tag in client_tags[:3]]  # Show up to 3 tags
            tag_display = ", ".join(tag_names)
            if len(client_tags) > 3:
                tag_display += f" (+{len(client_tags)-3} more)"
            self.table.setItem(row,8,QTableWidgetItem(tag_display))
            
            self.table.setItem(row,9,QTableWidgetItem(str(r["stripe_customer_id"] or "")))

    def on_row_select(self):
        items = self.table.selectedItems()
        if not items: return
        row = items[0].row()
        self.name.setText(self.table.item(row,1).text())
        self.email.setText(self.table.item(row,2).text())
        self.phone.setText(self.table.item(row,3).text())
        self.addr.setText(self.table.item(row,4).text())
        self.notes.setText(self.table.item(row,5).text())
        self.refresh_client_credit()

    def refresh_client_credit(self):
        """Update the credit display for the selected client"""
        row = self._selected_client_row()
        if row is None:
            self.lbl_credit.setText("Credit: $0.00")
            return
        
        client_id = int(self.table.item(row, 0).text())
        credit_cents = get_client_credit(self.conn, client_id)
        self.lbl_credit.setText(f"Credit: ${credit_cents/100:.2f}")

    def on_add_credit_clicked(self):
        """Handle adding credit to the selected client"""
        row = self._selected_client_row()
        if row is None:
            QMessageBox.information(self, "No Selection", "Please select a client first.")
            return
        
        client_id = int(self.table.item(row, 0).text())
        client_name = self.table.item(row, 1).text()
        
        amount, ok = QtWidgets.QInputDialog.getDouble(
            self, "Add Credit", 
            f"Enter credit amount for {client_name}:", 
            decimals=2, min=0.01, max=10000.00
        )
        
        if ok and amount > 0:
            amount_cents = int(amount * 100)
            add_client_credit(self.conn, client_id, amount_cents)
            self.refresh()
            self.refresh_client_credit()
            QMessageBox.information(self, "Credit Added", 
                f"Added ${amount:.2f} credit to {client_name}")

    def add_client(self):
        name = self.name.text().strip()
        if not name:
            QMessageBox.warning(self,"Missing","Client name required."); return
        email = self.email.text().strip()
        phone = self.phone.text().strip()
        addr = self.addr.text().strip()
        notes = self.notes.text().strip()
        sel = self.table.selectedItems()
        c = self.conn.cursor()
        if sel:
            cid = int(self.table.item(sel[0].row(),0).text())
            c.execute("UPDATE clients SET name=?,email=?,phone=?,address=?,notes=? WHERE id=?",
                      (name,email,phone,addr,notes,cid))
        else:
            c.execute("INSERT INTO clients(name,email,phone,address,notes)VALUES(?,?,?,?,?)",
                      (name,email,phone,addr,notes))
        self.conn.commit(); self.refresh()

    def delete_client(self):
        sel = self.table.selectedItems()
        if not sel: return
        cid = int(self.table.item(sel[0].row(),0).text())
        if QMessageBox.question(self,"Confirm",f"Delete client ID {cid}?")==QMessageBox.Yes:
            self.conn.execute("DELETE FROM clients WHERE id=?", (cid,)); self.conn.commit(); self.refresh()

    def _selected_client_row(self):
        items = self.table.selectedItems()
        if not items: return None
        return items[0].row()

    def open_selected_in_stripe(self):
        row = self._selected_client_row()
        if row is None: return
        cust_id_item = self.table.item(row,7)  # Fixed column index - StripeCustomerID is now column 7
        if not cust_id_item: return
        cust_id = cust_id_item.text().strip()
        if not cust_id: 
            QMessageBox.information(self,"No link","This client isn't linked to a Stripe customer."); return
        try:
            from stripe_integration import open_in_stripe
            open_in_stripe("customer", cust_id)
        except Exception as e:
            QMessageBox.critical(self,"Error",str(e))

    def sync_customers(self, show_message=True):
        from stripe_integration import list_all_customers
        try:
            customers = list_all_customers()  # ALL
        except Exception as e:
            if show_message:
                QMessageBox.critical(self,"Stripe error",str(e))
            return
        
        cur = self.conn.cursor()
        
        # Get existing clients by email (case-insensitive)
        existing_rows = cur.execute("SELECT id,email,stripe_customer_id FROM clients").fetchall()
        existing_by_email = { (r["email"] or "").strip().lower(): r for r in existing_rows if r["email"] }
        
        updates = 0
        imports = 0
        
        for customer in customers:
            email = (customer.get("email") or "").strip()
            if not email:
                continue
                
            email_lower = email.lower()
            stripe_id = customer.get("id")
            name = customer.get("name") or ""
            phone = customer.get("phone") or ""
            address = customer.get("address") or ""
            
            if email_lower in existing_by_email:
                # Update existing client with Stripe ID and additional data
                existing = existing_by_email[email_lower]
                if not existing["stripe_customer_id"]:
                    # New link - set Stripe ID and contact info
                    cur.execute("""
                        UPDATE clients SET stripe_customer_id=?, phone=?, address=? 
                        WHERE id=?
                    """, (stripe_id, phone, address, existing["id"]))
                    updates += 1
                else:
                    # Already linked - update contact info if we have new data
                    if phone or address:
                        cur.execute("""
                            UPDATE clients SET phone=?, address=? 
                            WHERE id=?
                        """, (phone, address, existing["id"]))
                        updates += 1
            else:
                # Import new customer from Stripe with all available data
                cur.execute("""
                    INSERT INTO clients(name,email,phone,address,stripe_customer_id) 
                    VALUES(?,?,?,?,?)
                """, (name, email, phone, address, stripe_id))
                imports += 1
        
        self.conn.commit()
        self.refresh()
        
        if show_message:
            message = []
            if updates > 0:
                message.append(f"Linked {updates} existing client(s)")
            if imports > 0:
                message.append(f"Imported {imports} new customer(s) from Stripe")
            
            if message:
                QMessageBox.information(self,"Stripe customers", " and ".join(message) + ".")
            else:
                QMessageBox.information(self,"Stripe customers","No new customers to import or link.")

    def link_selected_to_customer(self):
        row = self._selected_client_row()
        if row is None:
            QMessageBox.information(self,"Select a client","Pick a client row first."); return
        # simple dialog: enter customer ID or email match
        cust_id, ok = QtWidgets.QInputDialog.getText(self, "Link Stripe customer", "Paste Stripe Customer ID (starts with 'cus_') or email:")
        if not ok or not cust_id.strip():
            return
        val = cust_id.strip()
        if val.startswith("cus_"):
            self.conn.execute("UPDATE clients SET stripe_customer_id=? WHERE id=?", (val, int(self.table.item(row,0).text())))
            self.conn.commit(); self.refresh(); return
        # treat as email -> try to find via Stripe
        try:
            from stripe_integration import list_all_customers
            pool = list_all_customers()
            val_l = val.lower()
            match = next((c for c in pool if (c.get("email") or "").lower()==val_l), None)
            if not match:
                QMessageBox.information(self,"Not found","No Stripe customer with that email."); return
            self.conn.execute("UPDATE clients SET stripe_customer_id=? WHERE id=?", (match["id"], int(self.table.item(row,0).text())))
            self.conn.commit(); self.refresh()
        except Exception as e:
            QMessageBox.critical(self,"Stripe error",str(e))

# ---------------- Pets Tab ----------------
class PetsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.conn = get_conn()
        layout = QVBoxLayout(self)

        # Client selection
        top = QHBoxLayout()
        self.client_combo = QComboBox()
        self.reload_clients()
        top.addWidget(QLabel("Client:"))
        top.addWidget(self.client_combo)
        layout.addLayout(top)
        
        # Pet form
        form = QHBoxLayout()
        self.name = QLineEdit()
        self.species = QLineEdit()
        self.breed = QLineEdit()
        self.meds = QLineEdit()
        self.behaviour = QLineEdit()
        add_btn = QPushButton("Add Pet")
        add_btn.clicked.connect(self.add_pet)
        
        form.addWidget(QLabel("Name:"))
        form.addWidget(self.name)
        form.addWidget(QLabel("Species:"))
        form.addWidget(self.species)
        form.addWidget(QLabel("Breed:"))
        form.addWidget(self.breed)
        form.addWidget(QLabel("Meds:"))
        form.addWidget(self.meds)
        form.addWidget(QLabel("Behaviour:"))
        form.addWidget(self.behaviour)
        form.addWidget(add_btn)
        layout.addLayout(form)

        self.table = QTableWidget(0,7)
        self.table.setHorizontalHeaderLabels(["ID","Client","Name","Species","Breed","Meds","Behaviour"])
        layout.addWidget(self.table)
        self.refresh()

    def reload_clients(self):
        self.client_combo.clear()
        rows = self.conn.execute("SELECT id,name FROM clients ORDER BY name").fetchall()
        for r in rows:
            self.client_combo.addItem(f"{r['name']} (#{r['id']})", r['id'])

    def add_pet(self):
        idx = self.client_combo.currentIndex()
        if idx<0: QMessageBox.warning(self,"Missing","Create a client first."); return
        client_id = self.client_combo.currentData()
        name = self.name.text().strip()
        if not name: QMessageBox.warning(self,"Missing","Pet name required."); return
        species = self.species.text().strip() or "dog"
        breed = self.breed.text().strip()
        meds = self.meds.text().strip()
        behaviour = self.behaviour.text().strip()
        self.conn.execute("INSERT INTO pets(client_id,name,species,breed,meds,behaviour)VALUES(?,?,?,?,?,?)",
                          (client_id,name,species,breed,meds,behaviour))
        self.conn.commit(); self.refresh()

    def refresh(self):
        rows = self.conn.execute("""
        SELECT pets.id, clients.name AS client_name, pets.name, pets.species, pets.breed, pets.meds, pets.behaviour
        FROM pets JOIN clients ON pets.client_id=clients.id ORDER BY pets.id DESC
        """).fetchall()
        self.table.setRowCount(0)
        for r in rows:
            row = self.table.rowCount(); self.table.insertRow(row)
            vals = [r["id"], r["client_name"], r["name"], r["species"], r["breed"], r["meds"], r["behaviour"]]
            for i,v in enumerate(vals): self.table.setItem(row,i,QTableWidgetItem(str(v or "")))

# ---------------- Helper functions for BookingsTab ----------------
def _to_epoch(dt_qdatetime) -> int:
    # Normalize to UTC epoch seconds
    py = dt_qdatetime.toPython() if hasattr(dt_qdatetime, "toPython") else dt_qdatetime
    if py.tzinfo is None:
        from datetime import timezone
        py = py.replace(tzinfo=timezone.utc)
    return int(py.timestamp())

def _two_week_window():
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    start = datetime(datetime.now().year, now.month, now.day, tzinfo=timezone.utc)
    end = start.replace(hour=23, minute=59, second=59) + timedelta(days=13)
    return int(start.timestamp()), int(end.timestamp())

# ---------------- Line Items Dialog ----------------
class LineItemsDialog(QDialog):
    """
    A tiny editor for booking line items.
    catalog: list of {product_name, price_nickname, price_id, unit_amount_cents, display}
    Returns self.items: [{stripe_price_id, service_name, qty, unit_amount_cents}]
    """
    def __init__(self, catalog: list[dict], default_item=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Booking line items")
        self.catalog = catalog
        self.default_item = default_item
        self.items = []

        v = QVBoxLayout(self)
        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(["Service / price", "Qty", "Unit (AUD)", "Subtotal"])
        v.addWidget(self.table)

        btns = QHBoxLayout()
        self.add_btn = QPushButton("+ Add")
        self.del_btn = QPushButton("Delete")
        btns.addWidget(self.add_btn)
        btns.addWidget(self.del_btn)
        btns.addStretch()
        self.ok_btn = QPushButton("OK")
        self.cancel_btn = QPushButton("Cancel")
        btns.addWidget(self.ok_btn)
        btns.addWidget(self.cancel_btn)
        v.addLayout(btns)

        self.add_btn.clicked.connect(self.add_row)
        self.del_btn.clicked.connect(self.del_row)
        self.ok_btn.clicked.connect(self.accept_and_collect)
        self.cancel_btn.clicked.connect(self.reject)

        # one default row
        self.add_row()

    def add_row(self):
        r = self.table.rowCount()
        self.table.insertRow(r)

        # Service selector
        combo = QComboBox()
        for i, p in enumerate(self.catalog):
            # Make dialog tolerant - use fallback if display key missing
            label = p.get("display") or p.get("price_nickname") or p.get("label") or p.get("product_name", "Item")
            if not label or label == "Item":
                # Create a fallback label with price
                amount_cents = int(p.get("unit_amount_cents", 0) or p.get("amount_cents", 0))
                product_name = p.get("product_name", "Item")
                label = f"{product_name} - ${amount_cents/100:.2f}"
            combo.addItem(label, p)
        combo.currentIndexChanged.connect(lambda _: self._recalc_row(r))
        self.table.setCellWidget(r, 0, combo)

        # Qty
        qty = QSpinBox()
        qty.setMinimum(1)
        qty.setValue(1)
        qty.valueChanged.connect(lambda _: self._recalc_row(r))
        self.table.setCellWidget(r, 1, qty)

        # Unit (read-only text item)
        unit = QTableWidgetItem("$0.00")
        unit.setFlags(unit.flags() ^ Qt.ItemIsEditable)
        self.table.setItem(r, 2, unit)

        # Subtotal (read-only)
        sub = QTableWidgetItem("$0.00")
        sub.setFlags(sub.flags() ^ Qt.ItemIsEditable)
        self.table.setItem(r, 3, sub)

        self._recalc_row(r)

    def del_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def _recalc_row(self, r):
        combo = self.table.cellWidget(r, 0)
        qty = self.table.cellWidget(r, 1)
        if not combo or not qty:
            return
        meta = combo.currentData()
        unit_cents = int(meta.get("unit_amount_cents", 0))
        q = int(qty.value())
        self.table.item(r, 2).setText(self._fmt(unit_cents))
        self.table.item(r, 3).setText(self._fmt(unit_cents * q))

    def _fmt(self, cents: int) -> str:
        return f"${cents/100:.2f}"

    def accept_and_collect(self):
        out = []
        for r in range(self.table.rowCount()):
            combo = self.table.cellWidget(r, 0)
            qty = self.table.cellWidget(r, 1)
            if not combo or not qty:
                continue
            meta = combo.currentData()
            out.append({
                "stripe_price_id": meta["price_id"],
                "service_name": meta["display_short"],  # e.g. "Short Walk (Single)"
                "qty": int(qty.value()),
                "unit_amount_cents": int(meta.get("unit_amount_cents", 0)),
                "sort_order": r
            })
        self.items = out
        self.accept()

# ---------------- Enhanced Calendar Widget ----------------
class EnhancedCalendarWidget(QtWidgets.QCalendarWidget):
    """Calendar with colored dots for bookings/holds/admin tasks and no week numbers."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._markers = {}
        self.setGridVisible(True)
        self.setVerticalHeaderFormat(QtWidgets.QCalendarWidget.NoVerticalHeader)  # Hides week numbers
        self.setHorizontalHeaderFormat(QtWidgets.QCalendarWidget.ShortDayNames)

    def setMarkers(self, markers: dict):
        self._markers = markers or {}
        self.update()

    def paintCell(self, painter, rect, date):
        super().paintCell(painter, rect, date)
        key = date.toString("yyyy-MM-dd")
        info = self._markers.get(key)
        if not info:
            return
        colors = []
        if info.get('b'): colors.append(QtGui.QColor(26,115,232))   # bookings (blue)
        if info.get('h'): colors.append(QtGui.QColor(142,36,170))   # holds (purple)
        if info.get('a'): colors.append(QtGui.QColor(245,124,0))    # admin (orange)
        if not colors: return
        radius = max(3, min(rect.width(), rect.height()) // 12)
        margin = radius + 2
        total_w = len(colors) * (2*radius) + (len(colors)-1)*radius
        start_x = rect.center().x() - total_w//2
        y = rect.bottom() - margin
        painter.save()
        painter.setPen(QtCore.Qt.NoPen)
        for idx, col in enumerate(colors):
            painter.setBrush(col)
            cx = start_x + idx*(3*radius)
            painter.drawEllipse(QtCore.QPoint(cx, y), radius, radius)
        painter.restore()

# ---------------- Bookings Tab ----------------
class BookingsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.conn = get_conn()
        layout = QVBoxLayout(self)

        # Top toolbar with range selector and refresh
        top_layout = QHBoxLayout()
        self.rangeCombo = QComboBox()
        self.rangeCombo.addItems([
            "This week", "Next week",
            "Two weeks (this+next)",
            "Four weeks (this+3)",
            "This month", "Next month", "Month after",
            "Next 3 months"
        ])
        self.rangeCombo.currentIndexChanged.connect(self.refresh_two_weeks)
        top_layout.addWidget(QLabel("Range:"))
        top_layout.addWidget(self.rangeCombo)

        # REMOVED: Manual refresh/import buttons - bookings now auto-generated from subscriptions
        # self.refresh_btn = QPushButton("Refresh")
        # self.import_btn = QPushButton("Import from invoices")
        
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # Create form widgets
        form = QHBoxLayout()
        self.client_combo = QComboBox()
        self.service = QComboBox()
        # --- Multi-date table for multiple bookings ---
        self.multi_table = QTableWidget(0, 3)
        self.multi_table.setHorizontalHeaderLabels(["Date", "Start", "End"])
        hdr = self.multi_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Date column: shrink to fit
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)           # Start: take extra space
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)           # End: take extra space
        # initialize first row
        self._init_multi_row()

        # Add/Remove row buttons
        self.add_row_btn = QPushButton("Add date/time")
        self.remove_row_btn = QPushButton("Remove row")
        self.add_row_btn.clicked.connect(self.add_multi_row)
        self.remove_row_btn.clicked.connect(self.remove_selected_multi_row)

        # Create bookings button
        self.create_bookings_btn = QPushButton("Create bookings")
        self.create_bookings_btn.clicked.connect(self.create_multiple_bookings)
        self.location = QLineEdit()
        self.dogs = QSpinBox()
        self.dogs.setRange(1, 20)
        self.dogs.setValue(1)
        self.price = QSpinBox()
        self.price.setRange(0, 100000)
        self.price.setSuffix(" cents")
        self.notes = QLineEdit()
        
        refresh_services_btn = QPushButton("Refresh Services")
        refresh_services_btn.clicked.connect(self.load_services_from_stripe)
        add_btn = QPushButton("Add Booking")
        add_btn.clicked.connect(self.add_booking)
        
        self.reload_clients()
        self.load_services_from_stripe()
        
        # Wire handler for price sync when service changes
        self.service.currentIndexChanged.connect(self._sync_price_from_service)
        
        form.addWidget(QLabel("Client:"))
        form.addWidget(self.client_combo)
        form.addWidget(QLabel("Service:"))
        form.addWidget(self.service)
        form.addWidget(refresh_services_btn)
        form.addWidget(QLabel("Location:"))
        form.addWidget(self.location)
        form.addWidget(QLabel("Dogs:"))
        form.addWidget(self.dogs)
        form.addWidget(QLabel("Price:"))
        form.addWidget(self.price)
        form.addWidget(QLabel("Notes:"))
        form.addWidget(self.notes)
        form.addWidget(add_btn)
        
        # rebuild layout: original form fields + multi_table and buttons
        form_layout = QVBoxLayout()
        form_layout.addLayout(form)
        form_layout.addWidget(self.multi_table)
        row_btns = QHBoxLayout()
        row_btns.addWidget(self.add_row_btn)
        row_btns.addWidget(self.remove_row_btn)
        row_btns.addWidget(self.create_bookings_btn)
        row_btns.addStretch()
        form_layout.addLayout(row_btns)
        layout.addLayout(form_layout)

        # Line items row
        line_items_row = QHBoxLayout()
        self.line_items_btn = QPushButton("Line items…")
        self.line_items_btn.clicked.connect(self.open_line_items)
        line_items_row.addWidget(self.line_items_btn)
        line_items_row.addStretch()
        layout.addLayout(line_items_row)

        # Memory buffer for the booking being composed
        self.pending_items: list[dict] = []

        # Enhanced table with Conflicts column
        col_headers = ["ID","Client","Service","Start","End","Location","Dogs","Status","Price (AUD)","Notes","Conflicts"]
        self.table = QTableWidget(0, len(col_headers))
        self.table.setHorizontalHeaderLabels(col_headers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # Context menu on rows
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._open_row_menu)
        
        layout.addWidget(self.table)

        btns = QHBoxLayout()
        export_btn = QPushButton("Export all to .ics"); export_btn.clicked.connect(self.export_ics)
        export_sel_btn = QPushButton("Export selected to .ics"); export_sel_btn.clicked.connect(self.export_selected_ics)
        open_invoice_btn = QPushButton("Open invoice"); open_invoice_btn.clicked.connect(self.open_selected_invoice)
        del_btn = QPushButton("Delete selected"); del_btn.clicked.connect(self.delete_booking)
        for b in [export_btn, export_sel_btn, open_invoice_btn, del_btn]: btns.addWidget(b)
        layout.addLayout(btns)

        # Initialize with two-week view
        self.refresh_two_weeks()

    def _init_multi_row(self):
        """Insert the first row into multi_table with today's date and default times."""
        self.multi_table.setRowCount(1)
        self._populate_row_widgets(0)

    def add_multi_row(self):
        """Append a new row with date/time editors."""
        row = self.multi_table.rowCount()
        self.multi_table.insertRow(row)
        self._populate_row_widgets(row)

    def remove_selected_multi_row(self):
        """Remove selected row; ensure at least one row remains."""
        row = self.multi_table.currentRow()
        if row <= 0:
            return  # keep first row
        self.multi_table.removeRow(row)
        if self.multi_table.rowCount() == 0:
            self._init_multi_row()

    def _populate_row_widgets(self, row):
        """Populate date/time editors for the given row."""
        # Date column stays a QDateEdit
        date_edit = QDateEdit(QDate.currentDate())
        date_edit.setCalendarPopup(True)
        self.multi_table.setCellWidget(row, 0, date_edit)

        # Build a list of 48 half-hour times (00:00, 00:30, ..., 23:30)
        times = [
            (QTime(h, m).toString("hh:mm AP"), QTime(h, m))
            for h in range(24)
            for m in (0, 30)
        ]

        # Start time combo
        start_combo = QComboBox()
        for label, time_obj in times:
            start_combo.addItem(label, time_obj)
        # default selection can be current time rounded to nearest half hour
        now = QTime.currentTime()
        index = min(range(len(times)), key=lambda i: abs(times[i][1].secsTo(now)))
        start_combo.setCurrentIndex(index)

        # End time combo
        end_combo = QComboBox()
        for label, time_obj in times:
            end_combo.addItem(label, time_obj)
        # default one hour after start
        end_index = min(index + 2, len(times) - 1)
        end_combo.setCurrentIndex(end_index)

        self.multi_table.setCellWidget(row, 1, start_combo)
        self.multi_table.setCellWidget(row, 2, end_combo)

    def create_multiple_bookings(self):
        """Create one booking per row and apply credit across all bookings."""
        client_id = self.client_combo.currentData()
        if not client_id:
            QMessageBox.warning(self, "Missing", "Select a client first.")
            return
            
        service_data = self.service.currentData() or {}
        service_label = service_data.get("display") or service_data.get("price_nickname") or self.service.currentText()
        service_type = service_data.get("service_code") or service_label
        location = self.location.text().strip()
        dogs_count = self.dogs.value()
        price_cents = self.price.value() or int(service_data.get("amount_cents") or 0)
        notes = self.notes.text().strip() if hasattr(self.notes, "toPlainText") else self.notes.text().strip()
        
        # Calculate total cost and available credit
        total_bookings = self.multi_table.rowCount()
        total_cost_cents = price_cents * total_bookings
        credit_available = get_client_credit(self.conn, client_id)
        
        invoice_id = None
        total_credit_used = 0
        total_invoiced = 0
        
        try:
            with self.conn:
                remaining_credit = credit_available
                
                # Iterate over each row
                for row in range(self.multi_table.rowCount()):
                    qdate = self.multi_table.cellWidget(row, 0).date()
                    start_time = self.multi_table.cellWidget(row, 1).currentData()
                    end_time = self.multi_table.cellWidget(row, 2).currentData()
                    
                    start_dt = QDateTime(qdate, start_time)
                    end_dt = QDateTime(qdate, end_time)
                    
                    # check for overnight services and extend end time by one day
                    if "overnight" in service_label.lower() or "overnight" in service_type.lower():
                        end_dt = end_dt.addDays(1)
                    
                    start_iso = start_dt.toString("yyyy-MM-dd HH:mm:ss")
                    end_iso = end_dt.toString("yyyy-MM-dd HH:mm:ss")
                    
                    # Apply credit to this booking
                    price_due = price_cents
                    credit_for_this_booking = 0
                    
                    if remaining_credit >= price_cents:
                        # Pay entirely with credit
                        credit_for_this_booking = price_cents
                        price_due = 0
                        remaining_credit -= price_cents
                    elif remaining_credit > 0:
                        # Partial credit
                        credit_for_this_booking = remaining_credit
                        price_due = price_cents - remaining_credit
                        remaining_credit = 0
                    
                    # create booking
                    booking_id = add_or_upsert_booking(
                        self.conn, client_id, service_label, service_type,
                        start_iso, end_iso, location, dogs_count, price_due, notes
                    )
                    
                    total_credit_used += credit_for_this_booking
                    total_invoiced += price_due
                    
                    # create or reuse invoice only if there's an amount due
                    if price_due > 0:
                        if invoice_id is None:
                            from stripe_integration import ensure_draft_invoice_for_booking, push_invoice_items_from_booking
                            inv = ensure_draft_invoice_for_booking(self.conn, booking_id)
                            invoice_id = inv.id
                        else:
                            set_booking_invoice(self.conn, booking_id, invoice_id)
                        
                        push_invoice_items_from_booking(self.conn, booking_id, invoice_id)
                    else:
                        # Mark booking as paid by credit
                        set_booking_invoice(self.conn, booking_id, None)
                
                # Use the total credit at once
                if total_credit_used > 0:
                    use_client_credit(self.conn, client_id, total_credit_used)
                
                # Open invoice in dashboard if there's anything to invoice
                if invoice_id:
                    open_invoice_smart(invoice_id)
                
                self.refresh_two_weeks()
                
                # Show appropriate success message
                if total_credit_used > 0 and total_invoiced == 0:
                    QMessageBox.information(self, "Success",
                        f"{total_bookings} bookings created and paid entirely with ${total_credit_used/100:.2f} credit.")
                elif total_credit_used > 0:
                    QMessageBox.information(self, "Success",
                        f"{total_bookings} bookings created. ${total_credit_used/100:.2f} credit applied, ${total_invoiced/100:.2f} invoiced.")
                else:
                    QMessageBox.information(self, "Success",
                        f"{total_bookings} bookings created and invoiced for ${total_invoiced/100:.2f}.")
                                        
        except Exception as e:
            QMessageBox.critical(self, "Error creating bookings", str(e))

    def refresh_two_weeks(self):
        label = self.rangeCombo.currentText()
        start_dt, end_dt = resolve_range(label)
        
        # Use the canonical columns and proper range compare as specified
        self.range_start_iso = start_dt.isoformat()
        self.range_end_iso = end_dt.isoformat()
        self.refresh_table()

    def refresh_table(self):
        """Use the canonical query with proper JOINs as specified in the task"""
        c = self.conn.cursor()
        c.execute("""
            SELECT b.start_dt, b.end_dt,
                   c.name AS client,
                   COALESCE(c.address,'') AS address,
                   COALESCE(b.service, b.service_name, 'Service') AS service,
                   GROUP_CONCAT(p.name) AS pets,
                   b.id, b.location, b.dogs, b.status, b.price_cents, b.notes
              FROM bookings b
              JOIN clients c ON c.id = b.client_id
         LEFT JOIN booking_pets bp ON bp.booking_id = b.id
         LEFT JOIN pets p ON p.id = bp.pet_id
             WHERE date(b.start_dt) BETWEEN date(?) AND date(?)
               AND COALESCE(b.deleted,0)=0
          GROUP BY b.id, b.start_dt, b.end_dt, c.name, c.address, b.service, b.service_name
          ORDER BY b.start_dt
        """, (self.range_start_iso[:10], self.range_end_iso[:10]))
        
        rows = c.fetchall()
        self._populate_table_from_canonical_rows(rows)

    def _populate_table_from_canonical_rows(self, rows):
        """Populate table from canonical query results"""
        self.table.setRowCount(0)
        last_ws = None
        
        for r in rows:
            # Check if we need to insert a week separator
            if r["start_dt"]:
                try:
                    start_date = datetime.fromisoformat(r["start_dt"]).date()
                    ws = start_date - timedelta(days=start_date.weekday())  # Monday of this week
                    
                    if ws != last_ws and last_ws is not None:
                        # Insert a separator row
                        sep_row = self.table.rowCount()
                        self.table.insertRow(sep_row)
                        
                        # Create week separator item
                        week_end = ws + timedelta(days=6)
                        separator_text = f"Week of {ws.isoformat()} → {week_end.isoformat()}"
                        item = QTableWidgetItem(separator_text)
                        item.setFlags(Qt.ItemIsEnabled)  # non-editable
                        item.setBackground(QColor(45, 45, 55))
                        
                        # Span across all columns
                        self.table.setSpan(sep_row, 0, 1, self.table.columnCount())
                        self.table.setItem(sep_row, 0, item)
                    
                    last_ws = ws
                except:
                    pass  # Skip separator if date parsing fails
            
            # Insert the actual booking row
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            
            # Format price display - use price_cents from booking
            price_cents = r["price_cents"] or 0
            price_display = f"${price_cents/100:.2f}" if price_cents > 0 else ""
            
            # Set table items using canonical query results
            items = [
                str(r["id"] or ""),
                r["client"] or "",
                r["service"] or "",
                r["start_dt"] or "",
                r["end_dt"] or "",
                r["location"] or "",
                str(r["dogs"] or 1),
                r["status"] or "",
                price_display,
                r["notes"] or "",
                ""  # Conflicts column
            ]
            
            for col, item_text in enumerate(items):
                self.table.setItem(row_idx, col, QTableWidgetItem(item_text))

    def _populate_table_from_rows(self, rows):
        """Populate table from database rows with visual separators for week boundaries"""
        self.table.setRowCount(0)
        last_ws = None
        
        for r in rows:
            # Check if we need to insert a week separator
            if r["start"]:
                try:
                    start_date = datetime.fromisoformat(r["start"]).date()
                    ws = start_date - timedelta(days=start_date.weekday())  # Monday of this week
                    
                    if ws != last_ws and last_ws is not None:
                        # Insert a separator row
                        sep_row = self.table.rowCount()
                        self.table.insertRow(sep_row)
                        
                        # Create week separator item
                        week_end = ws + timedelta(days=6)
                        separator_text = f"Week of {ws.isoformat()} → {week_end.isoformat()}"
                        item = QTableWidgetItem(separator_text)
                        item.setFlags(Qt.ItemIsEnabled)  # non-editable
                        item.setBackground(QColor(45, 45, 55))
                        
                        # Span across all columns
                        self.table.setSpan(sep_row, 0, 1, self.table.columnCount())
                        self.table.setItem(sep_row, 0, item)
                    
                    last_ws = ws
                except:
                    pass  # Skip separator if date parsing fails
            
            # Insert the actual booking row
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            
            # Format price display
            price_cents = r["price_cents"] or 0
            price_display = f"${price_cents/100:.2f}" if price_cents > 0 else ""
            
            # Set table items
            items = [
                str(r["id"]),
                r["client"],
                r["service"],
                r["start"] or "",
                r["end"] or "",
                r["location"] or "",
                str(r["dogs"] or 1),
                r["status"],
                price_display,
                r["notes"],
                ""  # Conflicts column
            ]
            
            for col, item_text in enumerate(items):
                self.table.setItem(row_idx, col, QTableWidgetItem(item_text))

    def _populate_table(self, rows):
        self.table.setRowCount(0)
        for r in rows:
            # Skip subscription holds in Bookings table
            if r.get("status") == "hold" or str(r.get("id","")).startswith("sub-"):
                continue
                
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            
            # Format data for display
            client_name = r.get("client_name", "")
            service = r.get("service", "")
            start_dt = r.get("start_dt", "")
            end_dt = r.get("end_dt", "")
            location = r.get("location", "")
            dogs = str(r.get("dogs", 1))
            status = r.get("status", "")
            
            # Calculate price display
            price_display = ""
            if r.get("source") == "db":
                # For DB bookings, try to get price from booking_items
                try:
                    booking_id = r.get("id")
                    total_cents = booking_items_total_cents(self.conn, booking_id)
                    if total_cents > 0:
                        price_display = f"${total_cents/100:.2f}"
                except:
                    pass
            
            notes = r.get("notes", "")
            
            # Check for conflicts (simplified)
            conflicts = ""
            
            # Set table items
            items = [
                str(r.get("id", "")),
                client_name,
                service,
                start_dt,
                end_dt,
                location,
                dogs,
                status,
                price_display,
                notes,
                conflicts
            ]
            
            for col, item_text in enumerate(items):
                self.table.setItem(row_idx, col, QTableWidgetItem(item_text))

    def reload_clients(self):
        self.client_combo.clear()
        rows = self.conn.execute("SELECT id,name FROM clients ORDER BY name").fetchall()
        for r in rows:
            self.client_combo.addItem(f"{r['name']} (#{r['id']})", r['id'])

    def load_services_from_stripe(self):
        try:
            services = list_booking_services()
            self.service.clear()
            for s in services:
                display = s.get("display", s.get("price_nickname", "Unknown"))
                self.service.addItem(display, s)
            self._sync_price_from_service()
        except Exception as e:
            QMessageBox.warning(self, "Stripe Error", f"Could not load services: {e}")

    def _sync_price_from_service(self):
        try:
            data = self.service.currentData()
            cents = int((data or {}).get("amount_cents") or 0)
            if cents:
                self.price.setValue(cents)
        except Exception:
            pass

    def open_line_items(self):
        try:
            catalog = list_booking_services()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load services: {e}")
            return
        
        # Seed the dialog with the selected service
        default = self.service.currentData() or {}
        dialog = LineItemsDialog(catalog, default_item=default, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.pending_items = dialog.items

    def _create_invoice_and_open(self, booking_id, line_items=None):
        """Use the centralized function from stripe_integration.py"""
        from stripe_integration import _create_invoice_and_open
        return _create_invoice_and_open(self.conn, booking_id, line_items)

    def _show_week_of(self, start_iso: str):
        d = QDate.fromString(start_iso[:10], "yyyy-MM-dd")
        if not d.isValid():
            return
        monday = d.addDays(-(d.dayOfWeek() - 1))
        next_monday = monday.addDays(7)

        self.range_start_iso = QDateTime(monday, QTime(0, 0)).toString("yyyy-MM-dd HH:mm:ss")
        self.range_end_iso   = QDateTime(next_monday, QTime(0, 0)).toString("yyyy-MM-dd HH:mm:ss")
        self.refresh_table()

    def add_booking(self):
        # Import unified functions
        from unified_booking_helpers import get_canonical_service_info, create_booking_with_unified_fields
        
        # Disable button to prevent double-clicks
        add_btn = self.sender()
        if add_btn:
            add_btn.setEnabled(False)
        
        try:
            # validate a client is selected
            client_id = self.client_combo.currentData()
            if client_id is None:
                QMessageBox.warning(self, "Missing", "Select a client first.")
                return
            
            # FIXED: Use unified service info extraction
            service_data = self.service.currentData() or {}
            service_input = (service_data.get("display") or 
                           service_data.get("price_nickname") or 
                           service_data.get("product_name") or 
                           self.service.currentText() or 
                           "Dog Walking Service").strip()
            
            stripe_price_id = service_data.get("price_id")
            
            # read date/time from first row of multi_table
            qdate = self.multi_table.cellWidget(0, 0).date()
            start_time = self.multi_table.cellWidget(0, 1).currentData()
            end_time = self.multi_table.cellWidget(0, 2).currentData()
            
            start_dt = QDateTime(qdate, start_time)
            end_dt = QDateTime(qdate, end_time)
            
            # check for overnight services and extend end time by one day
            if "overnight" in service_input.lower():
                end_dt = end_dt.addDays(1)
            
            start_iso = start_dt.toString("yyyy-MM-dd HH:mm:ss")
            end_iso = end_dt.toString("yyyy-MM-dd HH:mm:ss")
            location = self.location.text().strip()
            dogs_count = max(1, self.dogs.value())  # Ensure at least 1 dog
            price_cents = self.price.value() or int(service_data.get("amount_cents") or 0)
            notes = self.notes.text().strip() if hasattr(self.notes, "toPlainText") else self.notes.text().strip()
            
            # Apply credit logic
            credit_available = get_client_credit(self.conn, client_id)
            price_due = price_cents
            credit_used = 0
            
            if credit_available >= price_cents:
                # Pay entirely with credit
                credit_used = price_cents
                price_due = 0
            elif credit_available > 0:
                # Partial credit
                credit_used = credit_available
                price_due = price_cents - credit_available
            
            # create booking inside a transaction using unified function
            with self.conn:
                booking_id = create_booking_with_unified_fields(
                    self.conn, client_id, service_input, start_iso, end_iso,
                    location, dogs_count, price_due, notes, stripe_price_id, 'manual'
                )
                
                # Use credit if any
                if credit_used > 0:
                    use_client_credit(self.conn, client_id, credit_used)
                
                if price_due > 0:
                    # Create invoice for the remainder
                    from stripe_integration import ensure_draft_invoice_for_booking, push_invoice_items_from_booking
                    inv = ensure_draft_invoice_for_booking(self.conn, booking_id)
                    push_invoice_items_from_booking(self.conn, booking_id, inv.id)
                    set_booking_invoice(self.conn, booking_id, inv.id)
                    open_invoice_smart(inv.id)
                else:
                    # Mark booking as paid by credit
                    set_booking_invoice(self.conn, booking_id, None)
            
            self.pending_items = []
            self._show_week_of(start_iso)
            
            # Show appropriate success message
            if credit_used > 0 and price_due == 0:
                QMessageBox.information(self, "Success",
                    f"Booking {booking_id} created and paid entirely with ${credit_used/100:.2f} credit.")
            elif credit_used > 0:
                QMessageBox.information(self, "Success",
                    f"Booking {booking_id} created. ${credit_used/100:.2f} credit applied, ${price_due/100:.2f} invoiced.")
            else:
                QMessageBox.information(self, "Success",
                    f"Booking {booking_id} created and invoiced for ${price_due/100:.2f}.")
                
        except Exception as e:
            QMessageBox.critical(self, "Invoice error", str(e))
        finally:
            if add_btn:
                add_btn.setEnabled(True)

    def _derive_service_type_from_label(self, label):
        """Derive a proper service_type code from a service label using central service map"""
        from service_map import get_service_code, DISPLAY_TO_SERVICE_CODE
        
        if not label:
            return "WALK_SHORT_SINGLE"  # Default fallback
        
        # First try exact match with the display name
        exact_match = get_service_code(label)
        if exact_match:
            return exact_match
        
        # If no exact match, try fuzzy matching for backward compatibility
        label_lower = label.lower().strip()
        
        # Try partial matching against all display names
        for display_name, service_code in DISPLAY_TO_SERVICE_CODE.items():
            if label_lower in display_name.lower():
                return service_code
        
        # Legacy mapping for common variations that might exist in old data
        if "daycare" in label_lower:
            if "pack" in label_lower and "5" in label_lower:
                return "DAYCARE_PACK5"
            elif "weekly" in label_lower:
                return "DAYCARE_WEEKLY"
            elif "fortnightly" in label_lower:
                return "DAYCARE_FORTNIGHTLY_PER_VISIT"
            else:
                return "DAYCARE_SINGLE"
        elif "walk" in label_lower:
            if "short" in label_lower:
                if "pack" in label_lower and "5" in label_lower:
                    return "WALK_SHORT_PACK5"
                elif "weekly" in label_lower:
                    return "WALK_SHORT_WEEKLY"
                else:
                    return "WALK_SHORT_SINGLE"
            elif "long" in label_lower:
                if "pack" in label_lower and "5" in label_lower:
                    return "WALK_LONG_PACK5"
                elif "weekly" in label_lower:
                    return "WALK_LONG_WEEKLY"
                else:
                    return "WALK_LONG_SINGLE"
        elif "home" in label_lower and "visit" in label_lower:
            if "2" in label_lower and "day" in label_lower:
                if "pack" in label_lower and "5" in label_lower:
                    return "HV_30_2X_PACK5"
                else:
                    return "HV_30_2X_SINGLE"
            else:
                if "pack" in label_lower and "5" in label_lower:
                    return "HV_30_1X_PACK5"
                else:
                    return "HV_30_1X_SINGLE"
        elif "pickup" in label_lower or "drop" in label_lower:
            if "fortnightly" in label_lower:
                return "PICKUP_FORTNIGHTLY_PER_VISIT"
            elif "weekly" in label_lower:
                return "PICKUP_WEEKLY_PER_VISIT"
            elif "pack" in label_lower and "5" in label_lower:
                return "PICKUP_DROPOFF_PACK5"
            else:
                return "PICKUP_DROPOFF"
        elif "scoop" in label_lower or "poop" in label_lower:
            if "twice" in label_lower and "weekly" in label_lower:
                return "SCOOP_TWICE_WEEKLY_MONTH"
            elif "fortnightly" in label_lower:
                return "SCOOP_FORTNIGHTLY_MONTH"
            elif "weekly" in label_lower:
                return "SCOOP_WEEKLY_MONTH"
            else:
                return "SCOOP_ONCE_SINGLE"
        elif "overnight" in label_lower or "sitting" in label_lower:
            if "pack" in label_lower and "5" in label_lower:
                return "BOARD_OVERNIGHT_PACK5"
            else:
                return "BOARD_OVERNIGHT_SINGLE"
        
        # Final fallback - return a safe default
        return "WALK_SHORT_SINGLE"

    def import_from_invoices(self):
        try:
            from stripe_invoice_bookings import import_invoice_bookings
            from subscription_sync import sync_subscriptions_to_bookings_and_calendar
            
            count = import_invoice_bookings(self.conn)
            
            # Use unified subscription sync instead of legacy promote function
            try:
                sync_stats = sync_subscriptions_to_bookings_and_calendar(self.conn)
                print(f"Unified subscription sync: {sync_stats}")
            except Exception as e:
                print("Unified subscription sync error:", e)
            
            self.refresh_two_weeks()
            QMessageBox.information(self, "Import Complete", f"Imported {count} bookings from invoices and synced subscriptions.")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def _open_row_menu(self, position):
        if self.table.itemAt(position) is None:
            return
        
        menu = QMenu()
        open_action = menu.addAction("Open invoice")
        delete_action = menu.addAction("Delete booking")
        
        action = menu.exec(self.table.mapToGlobal(position))
        if action == open_action:
            self.open_selected_invoice()
        elif action == delete_action:
            self.delete_booking()

    def on_open_invoice_clicked(self):
        row = self._selected_row()
        inv_id = row.get("stripe_invoice_id")
        if not inv_id:
            QMessageBox.warning(self, "No invoice", "This booking has no Stripe invoice.")
            return
        try:
            open_invoice_smart(inv_id)
        except Exception as e:
            QMessageBox.critical(self, "Invoice error", str(e))

    def _selected_row(self):
        """Helper method to get the selected row data as a dict"""
        row = self.table.currentRow()
        if row < 0:
            return {}
        
        booking_id = self.table.item(row, 0).text()
        try:
            # Get the booking data from database
            cur = self.conn.cursor()
            booking_row = cur.execute("""
                SELECT stripe_invoice_id, service, client_id
                FROM bookings WHERE id = ?
            """, (booking_id,)).fetchone()
            
            if booking_row:
                return {
                    "stripe_invoice_id": booking_row["stripe_invoice_id"],
                    "service": booking_row["service"],
                    "client_id": booking_row["client_id"]
                }
        except Exception:
            pass
        
        return {}

    def open_selected_invoice(self):
        row = self.table.currentRow()
        if row < 0:
            return
        
        booking_id = self.table.item(row, 0).text()
        try:
            # Use the centralized function from stripe_integration.py
            self._create_invoice_and_open(booking_id)
                
        except Exception as e:
            QMessageBox.critical(self, "Invoice error", str(e))

    def delete_booking(self):
        ids = [int(self.table.item(ix.row(), 0).text())
               for ix in self.table.selectionModel().selectedRows()]
        if not ids:
            return
        
        if QMessageBox.question(self, "Confirm", f"Delete {len(ids)} booking(s)?") == QMessageBox.Yes:
            try:
                placeholders = ",".join("?" * len(ids))
                self.conn.execute(f"UPDATE bookings SET deleted=1 WHERE id IN ({placeholders})", ids)
                self.conn.commit()
                self.refresh_two_weeks()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def export_ics(self):
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, "Export Calendar", "bookings.ics", "iCalendar files (*.ics)")
            if file_path:
                export_bookings(file_path)
                QMessageBox.information(self, "Export Complete", f"Calendar exported to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def export_selected_ics(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "No Selection", "Select a booking first.")
            return
        
        try:
            booking_id = self.table.item(row, 0).text()
            file_path, _ = QFileDialog.getSaveFileName(self, "Export Booking", f"booking_{booking_id}.ics", "iCalendar files (*.ics)")
            if file_path:
                export_bookings(file_path, [booking_id])
                QMessageBox.information(self, "Export Complete", f"Booking exported to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

# ---------------- Calendar Tab ----------------
class CalendarTab(QWidget):
    def __init__(self):
        super().__init__()
        self.conn = get_conn()
        layout = QVBoxLayout(self)

        # Add troubleshooting button only (removed legacy sync buttons per requirements)
        button_row = QHBoxLayout()
        
        self.troubleshoot_btn = QPushButton("Troubleshoot Sync")
        self.troubleshoot_btn.clicked.connect(self.troubleshoot_sync)
        self.troubleshoot_btn.setToolTip("Force manual sync if there are sync issues")
        button_row.addWidget(self.troubleshoot_btn)
        
        button_row.addStretch()
        layout.addLayout(button_row)

        top = QHBoxLayout()
        self.cal = EnhancedCalendarWidget()
        self.cal.setGridVisible(True)
        self.cal.setVerticalHeaderFormat(QtWidgets.QCalendarWidget.NoVerticalHeader)  # ensure hidden
        self.cal.selectionChanged.connect(self.refresh_day)
        top.addWidget(self.cal, 2)
        
        # Legend removed - no longer showing Bookings/Holds/Admin header
        
        try:
            self.cal.currentPageChanged.connect(self.rebuild_month_markers)
        except Exception:
            pass
        self.rebuild_month_markers()

        right = QVBoxLayout()
        self.capacity_label = QLabel("")
        right.addWidget(self.capacity_label)
        
        # Day details table
        self.table = QTableWidget(0, 6, self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Start", "End", "Client", "Address", "Service", "Pets"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        right.addWidget(self.table, 8)
        top.addLayout(right, 3)
        layout.addLayout(top)

        self.refresh_day()

    def rebuild_calendar_materialisation(self):
        cur = self.conn.cursor()

        # Always clear future occurrences for non-active subs
        cur.execute("""
            UPDATE sub_occurrences
               SET active = 0
             WHERE active = 1
               AND stripe_subscription_id IN (
                   SELECT stripe_subscription_id FROM subs
                   WHERE status NOT IN ('active','trialing')
               )
               AND date(start_dt) >= date('now')
        """)
        self.conn.commit()

        # Skip re-seeding entirely if there are no active subs
        cur.execute("SELECT COUNT(*) FROM subs WHERE status IN ('active','trialing')")
        (has_active,) = cur.fetchone()
        if not has_active:
            return  # nothing to materialise

        # If you already have helpers:
        clear_future_sub_occurrences(self.conn)   # (optionally scoped per sub)
        materialize_sub_occurrences(self.conn, horizon_days=90)

    def refresh_calendar(self):
        """
        Refresh calendar display without full sync.
        
        Updated to work with the new automatic sync workflow.
        This now just refreshes the display without performing subscription sync.
        """
        try:
            # Just refresh the current day view - no more subscription sync
            self.refresh_day()
            
            # Show brief confirmation
            QMessageBox.information(
                self, 
                "Calendar Refreshed", 
                "Calendar display has been refreshed.\n\nNote: Subscription sync now happens automatically when the app starts."
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Refresh Calendar Error", f"Failed to refresh calendar: {str(e)}")

    def troubleshoot_sync(self):
        """
        Troubleshooting sync method that forces a manual sync.
        
        This replaces the removed legacy sync buttons and should only be used
        when there are sync issues that need to be resolved manually.
        ENHANCED: Comprehensive error logging and status reporting.
        """
        try:
            from subscription_sync import sync_subscriptions_to_bookings_and_calendar
            from log_utils import log_subscription_info, log_subscription_error
            
            log_subscription_info("User initiated troubleshoot sync from calendar tab")
            
            # Show progress message
            progress_msg = QMessageBox(self)
            progress_msg.setWindowTitle("Troubleshoot Sync")
            progress_msg.setText("Performing troubleshooting sync...\nThis may take a moment.\n\nAll errors will be logged for debugging.")
            progress_msg.setStandardButtons(QMessageBox.NoButton)
            progress_msg.show()
            QApplication.processEvents()
            
            # Perform sync
            logger.info("Calendar: Starting troubleshoot sync")
            stats = sync_subscriptions_to_bookings_and_calendar(self.conn)
            
            # Close progress and refresh view
            progress_msg.close()
            self.refresh_day()
            
            # Enhanced results with error count
            success_msg = f"""Troubleshooting sync completed!

Subscriptions processed: {stats.get('subscriptions_processed', 0)}
Bookings created: {stats.get('bookings_created', 0)}
Bookings cleaned up: {stats.get('bookings_cleaned', 0)}
Errors encountered: {stats.get('errors_count', 0)}

Note: Subscriptions are now automatically synced when the app starts.
This troubleshooting sync should only be needed in case of sync issues.

Check the subscription error log for detailed error information."""
            
            log_subscription_info(f"Troubleshoot sync completed: {stats.get('bookings_created', 0)} bookings created, {stats.get('errors_count', 0)} errors")
            
            if stats.get('errors_count', 0) > 0:
                QMessageBox.warning(self, "Troubleshoot Sync Complete with Errors", success_msg)
            else:
                QMessageBox.information(self, "Troubleshoot Sync Complete", success_msg)
            
        except Exception as e:
            error_msg = f"Failed to perform troubleshooting sync: {str(e)}"
            logger.error(f"Calendar: {error_msg}")
            log_subscription_error("Calendar troubleshoot sync failed", "manual_sync", e)
            QMessageBox.critical(self, "Troubleshoot Sync Error", error_msg)

    def manual_subscription_sync(self):
        """
        Legacy method - now redirects to troubleshoot sync.
        
        This method is kept for compatibility but redirects to the new
        troubleshooting sync functionality.
        """
        # Redirect to troubleshoot sync with explanation
        reply = QMessageBox.question(
            self,
            "Manual Sync",
            "Manual subscription sync has been replaced with automatic sync on app startup.\n\n" +
            "Would you like to perform a troubleshooting sync instead?\n" +
            "(This should only be needed if there are sync issues)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.troubleshoot_sync()

    # REMOVED: No longer compute subscription holds - only show real bookings

    def refresh_day(self):
        # Clear table
        self.table.setRowCount(0)

        # Figure out the currently selected date in the grid
        day_dt = self.cal.selectedDate().toPython()

        # Pull fresh data - only show real bookings (no sub_occurrences)
        conn = get_conn()

        # FIXED: Only query real bookings with proper client and service joins
        bookings = conn.execute("""
            SELECT b.start_dt, b.end_dt,
                   c.name AS client,
                   COALESCE(c.address, '') AS address,
                   COALESCE(b.service, b.service_name, 'Service') AS service,
                   GROUP_CONCAT(p.name) AS pets
            FROM bookings b
            JOIN clients c ON c.id = b.client_id
            LEFT JOIN booking_pets bp ON bp.booking_id = b.id
            LEFT JOIN pets p ON p.id = bp.pet_id
            WHERE date(b.start_dt) = ? 
              AND COALESCE(b.deleted, 0) = 0
              AND (b.status IS NULL OR b.status NOT IN ('cancelled','canceled'))
            GROUP BY b.id, b.start_dt, b.end_dt, c.name, c.address, b.service, b.service_name
            ORDER BY b.start_dt
        """, (day_dt.strftime('%Y-%m-%d'),)).fetchall()

        # Populate the table with only real bookings
        for b in bookings:
            client_name = b["client"] or ""
            address = b["address"] or ""
            service = b["service"] or "Service"
            pets = b["pets"] or ""

            i = self.table.rowCount()
            self.table.insertRow(i)

            # Format datetime for display
            start_display = b["start_dt"] or ""
            end_display = b["end_dt"] or ""
            
            # Convert to readable format if possible
            try:
                if start_display:
                    start_dt = datetime.fromisoformat(start_display.replace('Z', '+00:00'))
                    start_display = start_dt.strftime("%H:%M")
                if end_display:
                    end_dt = datetime.fromisoformat(end_display.replace('Z', '+00:00'))
                    end_display = end_dt.strftime("%H:%M")
            except:
                pass  # Keep original format if parsing fails

            self.table.setItem(i, 0, QTableWidgetItem(start_display))  # Start
            self.table.setItem(i, 1, QTableWidgetItem(end_display))    # End
            self.table.setItem(i, 2, QTableWidgetItem(client_name))    # Client
            self.table.setItem(i, 3, QTableWidgetItem(address))        # Address
            self.table.setItem(i, 4, QTableWidgetItem(service))        # Service
            self.table.setItem(i, 5, QTableWidgetItem(pets))           # Pets

        conn.close()

    def rebuild_month_markers(self):
        # Compute visible month
        try:
            y = self.cal.yearShown(); m = self.cal.monthShown()
        except Exception:
            sel = self.cal.selectedDate(); y, m = sel.year(), sel.month()
        from datetime import date
        start = date(y, m, 1)
        end = date(y+1,1,1) if m==12 else date(y, m+1, 1)
        markers = {}
        c = self.conn.cursor()
        
        # Bookings per day (exclude cancelled/voided/deleted)
        try:
            c.execute("""
                SELECT date(start_dt) AS d, COUNT(*) AS n
                FROM bookings
                WHERE date(start_dt) >= ? AND date(start_dt) < ?
                  AND COALESCE(deleted,0)=0
                  AND (status IS NULL OR status NOT IN ('cancelled','canceled','void','voided'))
                GROUP BY date(start_dt)
            """, (start.isoformat(), end.isoformat()))
            for d, n in c.fetchall():
                markers.setdefault(d, {}).update({'b': n})
        except Exception:
            pass
            
        # Holds per day
        try:
            c.execute("""
                SELECT date(start_dt) AS d, COUNT(*) AS n
                FROM sub_occurrences
                WHERE active=1 AND date(start_dt) >= ? AND date(start_dt) < ?
                GROUP BY date(start_dt)
            """, (start.isoformat(), end.isoformat()))
            for d, n in c.fetchall():
                markers.setdefault(d, {}).update({'h': n})
        except Exception:
            pass
            
        # Admin due per day
        try:
            c.execute("""
                SELECT date(due_dt) AS d, COUNT(*) AS n
                FROM admin_events
                WHERE date(due_dt) >= ? AND date(due_dt) < ?
                GROUP BY date(due_dt)
            """, (start.isoformat(), end.isoformat()))
            for d, n in c.fetchall():
                markers.setdefault(d, {}).update({'a': n})
        except Exception:
            pass
            
        self.cal.setMarkers(markers)

# ---------------- Subscriptions Tab ----------------
class SubscriptionsTab(QWidget):
    rebuilt = Signal()
    
    def __init__(self):
        super().__init__()
        self.conn = get_conn()
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        
        # Keep essential button: subscription deletion only
        self.delete_btn = QPushButton("Delete Subscription")
        self.delete_btn.clicked.connect(self.delete_subscription)
        self.delete_btn.setStyleSheet("QPushButton { background-color: #dc3545; color: white; font-weight: bold; }")
        top.addWidget(self.delete_btn)
        layout.addLayout(top)

        # Information about the automatic workflow  
        info_label = QLabel("Subscriptions sync automatically on app startup and via webhooks. "
                           "Bookings and calendar entries are generated automatically when subscriptions are created/updated. "
                           "All operations are logged to subscription_error_log.txt for monitoring.")
        info_label.setStyleSheet("QLabel { color: #666; font-style: italic; padding: 10px; }")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self.table = QTableWidget(0,8)
        self.table.setHorizontalHeaderLabels(["ID","Customer","Status","Products","Days","Time","Dogs","Location"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemSelectionChanged.connect(self.on_row_select)
        layout.addWidget(self.table)

        # Load subscription data for display on startup
        self.refresh_from_stripe()

    def on_row_select(self):
        # Row selection handling - no longer needed with popup-based workflow
        pass

    def _mask_to_days_label(self, mask: int) -> str:
        names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        return ",".join(n for i,n in enumerate(names) if mask & (1<<i))

    def _clear_future_subscription_bookings(self, sub_id: str):
        """Clear future bookings for a specific subscription to avoid duplicates"""
        conn = get_conn()
        c = conn.cursor()
        
        # Clear future sub_occurrences for this subscription
        c.execute("""
            DELETE FROM sub_occurrences 
            WHERE stripe_subscription_id = ? 
            AND date(start_dt) >= date('now')
        """, (sub_id,))
        
        conn.commit()

    def _generate_bookings_for_sub(self, sub_id, client_id, service_code,
                                   days_mask, start_time_str, end_time_str,
                                   dogs, location, months_ahead=3):
        """Auto-generate bookings for subscriptions as specified in the task requirements"""
        conn = get_conn()
        cur = conn.cursor()
        # Remove future auto bookings for this sub
        cur.execute("""
            DELETE FROM bookings
            WHERE created_from_sub_id = ? AND date(start_dt) >= date('now')
              AND source = 'subscription'
        """, (sub_id,))
        conn.commit()
        
        # Build the next 3 months of dates
        def parse_hhmm(s):
            h, m = map(int, s.split(':')); return h, m
        sh, sm = parse_hhmm(start_time_str)
        eh, em = parse_hhmm(end_time_str)
        today = date.today()
        end_date = today + timedelta(days=90)
        created = 0
        for d in (today + timedelta(days=i) for i in range((end_date - today).days + 1)):
            if days_mask & (1 << d.weekday()):
                start_dt = datetime(d.year, d.month, d.day, sh, sm, tzinfo=BRISBANE)
                end_dt = datetime(d.year, d.month, d.day, eh, em, tzinfo=BRISBANE)
                if "overnight" in service_code.lower():
                    end_dt += timedelta(days=1)
                cur.execute("""
                    INSERT OR IGNORE INTO bookings
                    (client_id, service_type, start_dt, end_dt, location, dogs, status,
                     price_cents, notes, created_from_sub_id, source)
                    VALUES (?, ?, ?, ?, ?, ?, 'scheduled',
                            (SELECT amount_cents FROM services WHERE code=?), 
                            'Auto-generated from subscription', ?, 'subscription')
                """, (client_id, service_code, start_dt.isoformat(), end_dt.isoformat(),
                      location, dogs, service_code, sub_id))
                created += cur.rowcount or 0
        conn.commit()
        return created

    def _generate_subscription_bookings(self, sub_id: str, days_mask: int, start_str: str, end_str: str, dogs: int, location: str, notes: str) -> int:
        """Generate actual bookings from subscription schedule for the next 3 months"""
        from datetime import date, datetime, timedelta, time
        from subscription_utils import resolve_client_for_subscription, service_type_from_label
        
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo("Australia/Brisbane")
        except Exception:
            tz = None  # fall back to naive

        conn = get_conn()
        c = conn.cursor()
        
        # Get subscription details from Stripe to find the client AND service info
        try:
            import stripe
            from secrets_config import get_stripe_key
            stripe.api_key = get_stripe_key()
            
            # Get subscription with expanded data
            subscription = stripe.Subscription.retrieve(sub_id, expand=['customer', 'items.data.price.product'])
            
            # Use new unified client resolution
            client_id = resolve_client_for_subscription(conn, dict(subscription) if not isinstance(subscription, dict) else subscription)
            if not client_id:
                print(f"Could not resolve or create client for subscription {sub_id}")
                return 0

            # derive service_type and label from price/product metadata if available, else use fallback
            service_type = "WALK_GENERAL"
            service_label = "Dog Walking Service"
            try:
                items = getattr(subscription, 'items', None)
                if items and hasattr(items, 'data') and items.data:
                    item = items.data[0]
                    price = getattr(item, 'price', None)
                    nickname = getattr(price, 'nickname', None) if price else None
                    # prefer price/product metadata
                    if price and getattr(price, 'metadata', None):
                        md = dict(price.metadata or {})
                        service_type = md.get('service_code') or md.get('service_type') or service_type
                        service_label = md.get('service_name') or nickname or service_label
                    elif nickname:
                        service_label = nickname
                        service_type = service_type_from_label(service_label)
            except Exception as e:
                print(f"Warning: failed to extract service info for {sub_id}: {e}")
                        
        except Exception as e:
            print(f"Error getting subscription details: {e}")
            return 0

        # Time window - next 3 months
        today = date.today()
        end_date = today + timedelta(days=90)  # 3 months
        
        def parse_hhmm(s: str) -> time:
            hh, mm = map(int, s.split(":"))
            return time(hh, mm)

        st = parse_hhmm(start_str)
        et = parse_hhmm(end_str)
        
        bookings_created = 0
        d = today
        
        print(f"DEBUG: Generating bookings for subscription {sub_id}")
        print(f"DEBUG: days_mask = {days_mask} (binary: {bin(days_mask)})")
        print(f"DEBUG: Date range: {today} to {end_date}")
        print(f"DEBUG: client_id = {client_id}, service_type = {service_type}")
        
        while d <= end_date:
            weekday = d.weekday()  # Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
            day_matches = bool(days_mask & (1 << weekday))
            
            if day_matches:
                print(f"DEBUG: Day {d} (weekday {weekday}) matches schedule")
                
                if tz:
                    start_dt = datetime(d.year, d.month, d.day, st.hour, st.minute, tzinfo=tz)
                    end_dt = datetime(d.year, d.month, d.day, et.hour, et.minute, tzinfo=tz)
                else:
                    start_dt = datetime(d.year, d.month, d.day, st.hour, st.minute)
                    end_dt = datetime(d.year, d.month, d.day, et.hour, et.minute)

                start_dt_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
                end_dt_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")

                # Check for existing booking to avoid duplicates
                existing = c.execute("""
                    SELECT id FROM bookings 
                    WHERE client_id = ? 
                    AND start_dt = ? 
                    AND COALESCE(deleted, 0) = 0
                """, (client_id, start_dt_str)).fetchone()
                
                if not existing:
                    print(f"DEBUG: Creating booking for {start_dt_str}")
                    # FIXED: Create the booking with proper service info (not "SUBSCRIPTION")
                    price_cents = 0  # Subscription bookings are typically pre-paid
                    
                    booking_id = add_or_upsert_booking(
                        conn, client_id, service_label, service_type,
                        start_dt_str, end_dt_str, location, dogs, price_cents, 
                        f"Auto-generated from subscription {sub_id}. {notes}".strip()
                    )
                    bookings_created += 1
                    print(f"DEBUG: Created booking {booking_id}")
                else:
                    print(f"DEBUG: Booking already exists for {start_dt_str}")
            else:
                # Only print for first few days to avoid spam
                if (d - today).days < 7:
                    print(f"DEBUG: Day {d} (weekday {weekday}) does NOT match schedule (mask bit {weekday} = {bool(days_mask & (1 << weekday))})")

            d += timedelta(days=1)
        
        print(f"DEBUG: Total bookings created: {bookings_created}")

        conn.commit()
        return bookings_created

    def _derive_service_type_from_label(self, label):
        """Derive a proper service_type code from a service label"""
        if not label:
            return "WALK_GENERAL"
        
        label_lower = label.lower()
        
        # Map common service labels to proper service types
        if "daycare" in label_lower:
            if "single" in label_lower or "day" in label_lower:
                return "DAYCARE_SINGLE"
            elif "pack" in label_lower:
                return "DAYCARE_PACKS"
            elif "weekly" in label_lower:
                return "DAYCARE_WEEKLY_PER_VISIT"
            elif "fortnightly" in label_lower:
                return "DAYCARE_FORTNIGHTLY_PER_VISIT"
            else:
                return "DAYCARE_SINGLE"
        elif "short" in label_lower and "walk" in label_lower:
            if "pack" in label_lower:
                return "WALK_SHORT_PACKS"
            else:
                return "WALK_SHORT_SINGLE"
        elif "long" in label_lower and "walk" in label_lower:
            if "pack" in label_lower:
                return "WALK_LONG_PACKS"
            else:
                return "WALK_LONG_SINGLE"
        elif "home visit" in label_lower or "home-visit" in label_lower:
            if "30m" in label_lower and "2" in label_lower:
                return "HOME_VISIT_30M_2X_SINGLE"
            else:
                return "HOME_VISIT_30M_SINGLE"
        elif "pickup" in label_lower or "drop" in label_lower:
            return "PICKUP_DROPOFF_SINGLE"
        elif "scoop" in label_lower or "poop" in label_lower:
            if "weekly" in label_lower or "monthly" in label_lower:
                return "SCOOP_WEEKLY_MONTHLY"
            else:
                return "SCOOP_SINGLE"
        elif "walk" in label_lower:
            return "WALK_GENERAL"
        else:
            # Convert label to a reasonable service type code
            return label.upper().replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "")

    def _get_main_window(self):
        """Helper method to get the main window for UI refresh"""
        widget = self
        while widget:
            if isinstance(widget, MainWindow):
                return widget
            widget = widget.parent()
        return None

    def delete_subscription(self):
        """Delete selected subscription with confirmation dialog"""
        from unified_booking_helpers import delete_subscription_locally
        
        # 1) Ensure we have a selected row
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No selection", "Select a subscription row first.")
            return

        # 2) Get the subscription ID
        sub_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) or self.table.item(row, 0).text()
        if not sub_id or not sub_id.startswith("sub_"):
            QMessageBox.critical(self, "Delete failed", "Could not resolve Stripe subscription ID for this row.")
            return

        # 3) Get customer name for confirmation dialog
        customer_name = self.table.item(row, 1).text() if self.table.item(row, 1) else "Unknown Customer"
        
        # 4) Confirmation dialog
        reply = QMessageBox.question(
            self, 
            "Confirm Delete Subscription",
            f"Are you sure you want to delete this subscription and all future bookings?\n\n"
            f"Subscription: {sub_id}\n"
            f"Customer: {customer_name}\n\n"
            f"This action will:\n"
            f"• Remove all future bookings from this subscription\n"
            f"• Remove calendar entries\n"
            f"• Delete the subscription schedule\n\n"
            f"NOTE: This will only remove the subscription from the local database.\n"
            f"The subscription will remain active in Stripe and continue billing.\n\n"
            f"This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return

        # 5) Delete from local database first
        try:
            conn = get_conn()
            results = delete_subscription_locally(conn, sub_id)
            
            success_msg = f"Local deletion completed:\n"
            success_msg += f"• {results['bookings_deleted']} future bookings deleted\n"
            success_msg += f"• {results['calendar_entries_deleted']} calendar entries deleted\n"
            success_msg += f"• {results['schedules_deleted']} schedule entries deleted"
            
        except Exception as e:
            QMessageBox.critical(self, "Local Delete Failed", f"Error deleting local data: {str(e)}")
            return

        # 6) Remove from UI table
        self.table.removeRow(row)

        # 7) Refresh calendar and bookings to show changes
        main_window = self._get_main_window()
        if main_window:
            if hasattr(main_window, 'calendar_tab'):
                main_window.calendar_tab.rebuild_month_markers()
                main_window.calendar_tab.refresh_day()
            if hasattr(main_window, 'bookings_tab'):
                main_window.bookings_tab.refresh_two_weeks()

        # 8) Show success message
        QMessageBox.information(self, "Subscription Deleted", success_msg)

        # 9) Trigger automatic sync to fetch any missing subscriptions
        try:
            # This will fetch subscriptions from Stripe and show dialogs for any missing data
            from startup_sync import SubscriptionAutoSync
            self.auto_sync = SubscriptionAutoSync()
            self.auto_sync.perform_startup_sync(show_progress=False)
        except Exception as e:
            print(f"Auto-sync after deletion failed: {e}")

    def refresh_from_stripe(self):
        try:
            subs = list_subscriptions()
            self.table.setRowCount(0)
            for s in subs:
                row = self.table.rowCount(); self.table.insertRow(row)
                sub_id = s.get("id", "")
                
                self.table.setItem(row,0,QTableWidgetItem(sub_id))
                self.table.setItem(row,1,QTableWidgetItem(s.get("customer_name","")))
                self.table.setItem(row,2,QTableWidgetItem(s.get("status","")))
                self.table.setItem(row,3,QTableWidgetItem(s.get("products","")))
                
                # Load schedule data from local database
                schedule_data = self._load_schedule_for_subscription(sub_id)
                self.table.setItem(row,4,QTableWidgetItem(schedule_data.get("days_display", "")))
                self.table.setItem(row,5,QTableWidgetItem(schedule_data.get("time_display", "")))
                self.table.setItem(row,6,QTableWidgetItem(str(schedule_data.get("dogs", ""))))
                self.table.setItem(row,7,QTableWidgetItem(schedule_data.get("location", "")))
        except Exception as e:
            QMessageBox.critical(self,"Stripe Error",str(e))
    
    def _load_schedule_for_subscription(self, subscription_id: str) -> dict:
        """Load schedule data from local database for a subscription."""
        try:
            if not subscription_id:
                return {}
                
            # Query the subs_schedule table for this subscription
            schedule = self.conn.execute("""
                SELECT days, start_time, end_time, dogs, location, notes
                FROM subs_schedule
                WHERE stripe_subscription_id = ?
            """, (subscription_id,)).fetchone()
            
            if not schedule:
                return {}
            
            # Format the data for display
            result = {
                "days_display": self._format_days_for_display(schedule["days"] or ""),
                "time_display": self._format_time_for_display(schedule["start_time"] or "", schedule["end_time"] or ""),
                "dogs": schedule["dogs"] or 0,
                "location": schedule["location"] or ""
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error loading schedule for subscription {subscription_id}: {e}")
            return {}
    
    def _format_days_for_display(self, days_csv: str) -> str:
        """Format days CSV into display format."""
        if not days_csv:
            return ""
        
        # Map day codes to short names
        day_map = {
            "MON": "Mon", "TUE": "Tue", "WED": "Wed", "THU": "Thu",
            "FRI": "Fri", "SAT": "Sat", "SUN": "Sun"
        }
        
        days = [day.strip().upper() for day in days_csv.split(",") if day.strip()]
        display_days = [day_map.get(day, day) for day in days if day in day_map]
        
        return ", ".join(display_days)
    
    def _format_time_for_display(self, start_time: str, end_time: str) -> str:
        """Format time range for display."""
        if not start_time or not end_time:
            return ""
        
        try:
            # Parse and format times to ensure consistent display
            from datetime import time, datetime
            
            start = datetime.strptime(start_time, "%H:%M").time()
            end = datetime.strptime(end_time, "%H:%M").time()
            
            return f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
            
        except Exception:
            # Fallback if parsing fails
            return f"{start_time}-{end_time}" if start_time and end_time else ""

# ---------------- Archive Tab ----------------
class ArchiveTab(QWidget):
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Invoice", "Date", "Client", "Service", "Total", "Open"])
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self):
        cur = self.conn.cursor()
        # "Past" = invoices whose booking start is before the first day of the current month
        cur.execute("""
          SELECT b.stripe_invoice_id, DATE(b.start) AS d, COALESCE(c.name, ''), b.service, 
                 COALESCE(b.price_cents,0), b.id
            FROM bookings b
            LEFT JOIN clients c ON c.id=b.client_id
           WHERE b.stripe_invoice_id IS NOT NULL
             AND DATE(b.start) < DATE('now','start of month')
             AND COALESCE(b.deleted,0)=0
           ORDER BY d DESC
        """)
        rows = cur.fetchall()
        self.table.setRowCount(0)
        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(r[0] or ""))        # invoice id
            self.table.setItem(i, 1, QTableWidgetItem(r[1] or ""))        # date
            self.table.setItem(i, 2, QTableWidgetItem(r[2] or ""))        # client
            self.table.setItem(i, 3, QTableWidgetItem(r[3] or ""))        # service
            self.table.setItem(i, 4, QTableWidgetItem(f"${(r[4] or 0)/100:.2f}"))
            btn = QPushButton("Open in Stripe")
            btn.clicked.connect(lambda _=None, inv=r[0]: self._open_invoice(inv))
            self.table.setCellWidget(i, 5, btn)

    def _open_invoice(self, invoice_id: str):
        import webbrowser, stripe
        try:
            from secrets_config import get_stripe_key
            stripe.api_key = get_stripe_key()
            base = "https://dashboard.stripe.com"
            if getattr(stripe, "api_key", "").startswith("sk_test_"):
                base += "/test"
            webbrowser.open(f"{base}/invoices/{invoice_id}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open invoice: {e}")

# ---------------- Admin Tab ----------------
class AdminTab(QWidget):
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)

        # --- Google Calendar group
        g = QGroupBox("Google Calendar")
        gl = QHBoxLayout(g)
        self.lbl_google = QLabel("Status: not connected")
        self.btn_pick_creds = QPushButton("Connect Google…")
        self.btn_pick_creds.clicked.connect(self.connect_google)
        self.btn_open_token = QPushButton("Open token file")
        self.btn_open_token.clicked.connect(self.open_token)
        gl.addWidget(self.lbl_google); gl.addStretch(1)
        gl.addWidget(self.btn_pick_creds); gl.addWidget(self.btn_open_token)
        layout.addWidget(g)

        # --- Stripe Settings group
        stripe_group = QGroupBox("Stripe Settings")
        stripe_layout = QHBoxLayout(stripe_group)
        self.lbl_stripe = QLabel("Status: checking...")
        self.btn_change_stripe_key = QPushButton("Change Stripe Key")
        self.btn_change_stripe_key.clicked.connect(self.change_stripe_key)
        self.btn_check_stripe_status = QPushButton("Check Status")
        self.btn_check_stripe_status.clicked.connect(self.check_stripe_status)
        stripe_layout.addWidget(self.lbl_stripe); stripe_layout.addStretch(1)
        stripe_layout.addWidget(self.btn_check_stripe_status); stripe_layout.addWidget(self.btn_change_stripe_key)
        layout.addWidget(stripe_group)

        # --- Django Server group
        django_group = QGroupBox("Django Server")
        django_layout = QHBoxLayout(django_group)
        self.lbl_django_status = QLabel("Status: Stopped")
        self.lbl_django_status.setStyleSheet("color: orange;")
        self.btn_start_server = QPushButton("Start Server")
        self.btn_start_server.clicked.connect(self.start_django_server)
        self.btn_stop_server = QPushButton("Stop Server")
        self.btn_stop_server.clicked.connect(self.stop_django_server)
        self.btn_stop_server.setEnabled(False)
        django_layout.addWidget(self.lbl_django_status); django_layout.addStretch(1)
        django_layout.addWidget(self.btn_start_server); django_layout.addWidget(self.btn_stop_server)
        layout.addWidget(django_group)

        # --- Admin tasks group
        t = QGroupBox("Admin tasks")
        tl = QVBoxLayout(t)
        row = QHBoxLayout()
        self.inp_title = QLineEdit(); self.inp_title.setPlaceholderText("Task title")
        self.inp_date  = QDateEdit(); self.inp_date.setCalendarPopup(True)
        self.inp_date.setDate(QDate.currentDate())
        self.inp_notes = QLineEdit(); self.inp_notes.setPlaceholderText("Notes (optional)")
        self.btn_add   = QPushButton("Add task"); self.btn_add.clicked.connect(self.add_task)
        row.addWidget(self.inp_title); row.addWidget(self.inp_date); row.addWidget(self.inp_notes); row.addWidget(self.btn_add)
        tl.addLayout(row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID","Title","Due date","Completed"])
        self.table.horizontalHeader().setStretchLastSection(True)
        tl.addWidget(self.table)

        tools = QHBoxLayout()
        self.btn_mark = QPushButton("Mark completed (selected)"); self.btn_mark.clicked.connect(self.mark_completed)
        self.btn_del  = QPushButton("Delete selected");           self.btn_del .clicked.connect(self.delete_selected)
        tools.addWidget(self.btn_mark); tools.addWidget(self.btn_del); tools.addStretch(1)
        tl.addLayout(tools)

        layout.addWidget(t); layout.addStretch(1)
        
        # --- Django server management
        self.django_process = None
        self.django_server_timer = QTimer()
        self.django_server_timer.timeout.connect(self.check_django_server_status)
        self.django_server_timer.start(2000)  # Check every 2 seconds
        
        self.refresh_google_status(); self.refresh_stripe_status(); self.refresh_table()

    # --- Google helpers (lazy imports so the tab never crashes)
    def refresh_google_status(self):
        from pathlib import Path
        self.lbl_google.setText("Status: connected" if Path("google_token.json").exists() else "Status: not connected")

    def connect_google(self):
        try:
            path, _ = QFileDialog.getOpenFileName(self, "Select Google credentials.json", "", "JSON files (*.json)")
            if not path: return
            # Import only when needed
            from google_sync import get_service
            get_service(path)  # runs OAuth; creates google_token.json on success
            QMessageBox.information(self, "Google", "Google account connected.")
            self.refresh_google_status()
        except Exception as e:
            QMessageBox.warning(self, "Google connect failed", str(e))

    def open_token(self):
        import os, webbrowser
        p = os.path.abspath("google_token.json")
        if os.path.exists(p): webbrowser.open(f"file:///{p}")
        else: QMessageBox.information(self, "Token", "No token yet. Connect Google first.")

    # --- Stripe helpers
    def refresh_stripe_status(self):
        """Update the Stripe status label based on current key status"""
        try:
            from stripe_key_manager import get_key_status
            status = get_key_status()
            
            if status["key_stored"]:
                key_type = status["key_type"]
                self.lbl_stripe.setText(f"Status: {key_type} key configured")
                self.lbl_stripe.setStyleSheet("color: green;")
            else:
                self.lbl_stripe.setText("Status: no key configured")
                self.lbl_stripe.setStyleSheet("color: orange;")
        except Exception as e:
            self.lbl_stripe.setText(f"Status: error checking ({e})")
            self.lbl_stripe.setStyleSheet("color: red;")

    def check_stripe_status(self):
        """Show detailed Stripe key status information"""
        try:
            from stripe_key_manager import get_key_status
            status = get_key_status()
            
            details = []
            details.append(f"Key stored: {'Yes' if status['key_stored'] else 'No'}")
            if status['key_stored']:
                details.append(f"Key type: {status['key_type']}")
            details.append(f"Storage method: {status['storage_method']}")
            details.append(f"GUI available: {'Yes' if status['gui_available'] else 'No'}")
            details.append(f"Keyring available: {'Yes' if status['keyring_available'] else 'No'}")
            
            QMessageBox.information(
                self, 
                "Stripe Key Status", 
                "\n".join(details)
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to check Stripe status: {e}")

    def change_stripe_key(self):
        """Prompt user to enter a new Stripe key and update it"""
        try:
            from stripe_key_manager import update_stripe_key
            import stripe
            
            # Confirm with user first
            reply = QMessageBox.question(
                self, 
                "Change Stripe Key", 
                "This will replace your current Stripe API key.\n\n"
                "Make sure you have your new Stripe secret key ready.\n"
                "Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                if update_stripe_key():
                    # Update the Stripe module with the new key
                    from stripe_key_manager import get_stripe_key
                    new_key = get_stripe_key()
                    stripe.api_key = new_key
                    
                    # Update the status display
                    self.refresh_stripe_status()
                    
                    QMessageBox.information(
                        self, 
                        "Success", 
                        "Stripe API key updated successfully!"
                    )
                else:
                    QMessageBox.warning(
                        self, 
                        "Cancelled", 
                        "Stripe key update was cancelled or failed."
                    )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update Stripe key: {e}")

    # --- Admin tasks CRUD (schema now handled in db.py)

    def refresh_table(self):
        c = self.conn.cursor()
        c.execute("SELECT id,title,due_dt,completed FROM admin_events ORDER BY date(due_dt) ASC, id DESC")
        rows = c.fetchall()
        self.table.setRowCount(0)
        for r in rows:
            i = self.table.rowCount(); self.table.insertRow(i)
            self.table.setItem(i,0,QTableWidgetItem(str(r[0])))
            self.table.setItem(i,1,QTableWidgetItem(str(r[1])))
            self.table.setItem(i,2,QTableWidgetItem(str(r[2])))
            self.table.setItem(i,3,QTableWidgetItem("Yes" if int(r[3]) else "No"))

    def add_task(self):
        title = self.inp_title.text().strip()
        if not title:
            QMessageBox.information(self, "Missing", "Enter a task title."); return
        due   = self.inp_date.date().toString("yyyy-MM-dd")
        notes = self.inp_notes.text().strip()
        self.conn.execute("INSERT INTO admin_events(title,due_dt,notes,completed) VALUES (?,?,?,0)", (title, due, notes))
        self.conn.commit(); self.inp_title.clear(); self.inp_notes.clear(); self.refresh_table()

    def _selected_ids(self):
        return [int(self.table.item(ix.row(),0).text()) for ix in self.table.selectionModel().selectedRows()]

    def mark_completed(self):
        ids = self._selected_ids()
        if not ids: return
        self.conn.execute(f"UPDATE admin_events SET completed=1 WHERE id IN ({','.join(map(str,ids))})")
        self.conn.commit(); self.refresh_table()

    def delete_selected(self):
        ids = self._selected_ids()
        if not ids: return
        self.conn.execute(f"DELETE FROM admin_events WHERE id IN ({','.join(map(str,ids))})")
        self.conn.commit(); self.refresh_table()

    # --- Django Server management methods
    def start_django_server(self):
        """Start the Django development server"""
        if self.django_process and self.django_process.poll() is None:
            QMessageBox.information(self, "Server Already Running", "Django server is already running.")
            return
            
        try:
            # Prepare environment with dummy Stripe key to avoid prompts
            env = {
                **os.environ,
                "DJANGO_SETTINGS_MODULE": "dogwalking_django.settings",
                "STRIPE_SECRET_KEY": "sk_test_dummy_for_server_startup",  # Dummy key to avoid interactive prompt
                "PYTHONHTTPSVERIFY": "0",  # Skip SSL verification in development
                "SKIP_STRIPE_SYNC": "1"  # Skip automatic Stripe sync during development server
            }
            
            # Start server in a separate thread to avoid blocking UI
            def run_server():
                try:
                    self.django_process = subprocess.Popen(
                        [sys.executable, "manage.py", "runserver", "--noreload", "127.0.0.1:8000"],
                        cwd=os.path.dirname(os.path.abspath(__file__)),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.PIPE,
                        env=env
                    )
                    
                    # Send empty input to skip any remaining prompts
                    if self.django_process.stdin:
                        try:
                            self.django_process.stdin.write(b"\n")
                            self.django_process.stdin.flush()
                            self.django_process.stdin.close()
                        except:
                            pass
                        
                except Exception as e:
                    self.show_server_error(f"Failed to start Django server: {e}")
                    return
                    
            # Run server in thread
            server_thread = threading.Thread(target=run_server, daemon=True)
            server_thread.start()
            
            # Give server time to start
            self.update_server_status("Starting...", "blue")
            QTimer.singleShot(5000, self.verify_server_started)
            
        except Exception as e:
            self.show_server_error(f"Failed to start Django server: {e}")

    def verify_server_started(self):
        """Verify server started successfully after delay"""
        if self.django_process:
            if self.django_process.poll() is None:  # Still running
                # Check if server is actually responding
                try:
                    import urllib.request
                    urllib.request.urlopen("http://127.0.0.1:8000", timeout=2)
                    self.update_server_status("Running", "green")
                    self.btn_start_server.setEnabled(False)
                    self.btn_stop_server.setEnabled(True)
                    QMessageBox.information(self, "Server Started", 
                        "Django development server started successfully!\n\n"
                        "You can access it at: http://127.0.0.1:8000")
                    return
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        # 404 means server is running but no route configured - that's fine
                        self.update_server_status("Running", "green")
                        self.btn_start_server.setEnabled(False)
                        self.btn_stop_server.setEnabled(True)
                        QMessageBox.information(self, "Server Started", 
                            "Django development server started successfully!\n\n"
                            "You can access it at: http://127.0.0.1:8000\n"
                            "(404 response is normal - no root URL configured)")
                        return
                    else:
                        # Other HTTP errors - server may still be starting
                        self.update_server_status("Starting...", "blue")
                        QTimer.singleShot(3000, self.verify_server_started)
                        return
                except:
                    # Process running but not responding yet - may still be starting
                    self.update_server_status("Starting...", "blue")
                    # Check again in a few seconds
                    QTimer.singleShot(3000, self.verify_server_started)
                    return
                    
            else:  # Process exited
                try:
                    stderr_output = self.django_process.stderr.read().decode('utf-8', errors='ignore')
                    stdout_output = self.django_process.stdout.read().decode('utf-8', errors='ignore')
                    
                    # Check for common error patterns
                    if "port is already in use" in stderr_output.lower() or "address already in use" in stderr_output.lower():
                        self.show_server_error("Port 8000 is already in use.\n\nPlease stop any existing server running on this port, or the server may already be running externally.")
                    elif "no module named 'django'" in stderr_output.lower():
                        self.show_server_error("Django is not installed.\n\nPlease install Django requirements:\npip install -r requirements-django.txt")
                    elif "permission denied" in stderr_output.lower():
                        self.show_server_error("Permission denied when starting server.\n\nPlease check file permissions or try running as administrator.")
                    elif "error" in stderr_output.lower() and len(stderr_output.strip()) > 0:
                        self.show_server_error(f"Server failed to start with error:\n\n{stderr_output[:800]}")
                    else:
                        # Server might have exited normally during startup (e.g., Django issues)
                        if "Quit the server with CONTROL-C" in stdout_output:
                            # Server actually started successfully
                            self.update_server_status("Running", "green")
                            self.btn_start_server.setEnabled(False)
                            self.btn_stop_server.setEnabled(True)
                            return
                        else:
                            self.show_server_error(f"Server exited unexpectedly:\n\nSTDOUT:\n{stdout_output[:400]}\n\nSTDERR:\n{stderr_output[:400]}")
                except Exception as e:
                    self.show_server_error(f"Server failed to start: {e}")
                    
                self.django_process = None
                self.update_server_status("Error", "red")
                
    def stop_django_server(self):
        """Stop the Django development server"""
        if not self.django_process:
            QMessageBox.information(self, "No Server Running", "No Django server is currently running.")
            return
            
        try:
            # Try graceful termination first
            self.django_process.terminate()
            
            # Wait a moment for graceful shutdown
            try:
                self.django_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if graceful shutdown failed
                try:
                    self.django_process.kill()
                    self.django_process.wait(timeout=2)
                except:
                    pass
                    
            self.django_process = None
            self.update_server_status("Stopped", "orange")
            self.btn_start_server.setEnabled(True)
            self.btn_stop_server.setEnabled(False)
            
            QMessageBox.information(self, "Server Stopped", "Django server stopped successfully.")
            
        except Exception as e:
            self.show_server_error(f"Failed to stop Django server: {e}")
            
    def check_django_server_status(self):
        """Check Django server status periodically"""
        if self.django_process:
            if self.django_process.poll() is None:  # Still running
                # Check if it's actually responsive (but don't fail status if not)
                try:
                    import urllib.request
                    with urllib.request.urlopen("http://127.0.0.1:8000", timeout=2) as response:
                        if response.status == 200:
                            self.update_server_status("Running", "green")
                            self.btn_start_server.setEnabled(False)
                            self.btn_stop_server.setEnabled(True)
                            return
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        # 404 means server is running but no route configured - that's fine
                        self.update_server_status("Running", "green")
                        self.btn_start_server.setEnabled(False)
                        self.btn_stop_server.setEnabled(True)
                        return
                except:
                    pass
                    
                # Process running but may not be responsive yet
                current_status = self.lbl_django_status.text()
                if "Starting..." not in current_status:
                    self.update_server_status("Running", "green")
                    self.btn_start_server.setEnabled(False)
                    self.btn_stop_server.setEnabled(True)
            else:  # Process died
                self.django_process = None
                self.update_server_status("Stopped", "orange")
                self.btn_start_server.setEnabled(True)
                self.btn_stop_server.setEnabled(False)
        else:
            # No process, check if server running on port anyway (external server)
            try:
                import urllib.request
                with urllib.request.urlopen("http://127.0.0.1:8000", timeout=1) as response:
                    if response.status == 200:
                        self.update_server_status("Running (External)", "yellow")
                        self.btn_start_server.setEnabled(False)
                        self.btn_stop_server.setEnabled(False)
                        return
            except:
                pass
                
            # No server running
            self.update_server_status("Stopped", "orange")
            self.btn_start_server.setEnabled(True)
            self.btn_stop_server.setEnabled(False)
            
    def update_server_status(self, status_text, color):
        """Update server status label"""
        self.lbl_django_status.setText(f"Status: {status_text}")
        self.lbl_django_status.setStyleSheet(f"color: {color};")
        
    def show_server_error(self, message):
        """Show server error dialog"""
        QMessageBox.critical(self, "Django Server Error", message)

# ---------------- Main Window ----------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Farm Dog Walking App")
        self.setGeometry(100, 100, 1400, 900)
        
        # Apply dark theme
        try:
            self._apply_dim_dark_theme()
        except Exception as e:
            print("Theme error:", e)
        
        # Initialize database
        init_db()
        self.conn = get_conn()
        
        # Create central widget and tabs
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Add tabs
        self.crm_dashboard = CRMDashboardTab()
        self.clients_tab = ClientsTab()
        self.pets_tab = PetsTab()
        self.bookings_tab = BookingsTab()
        self.calendar_tab = CalendarTab()
        self.subscriptions_tab = SubscriptionsTab()
        self.reports_tab = ReportsTab()
        self.archive_tab = ArchiveTab(get_conn())
        
        self.tabs.addTab(self.crm_dashboard, "CRM Dashboard")
        self.tabs.addTab(self.clients_tab, "Clients")
        self.tabs.addTab(self.pets_tab, "Pets")
        self.tabs.addTab(self.bookings_tab, "Bookings")
        self.tabs.addTab(self.calendar_tab, "Calendar")
        self.tabs.addTab(self.subscriptions_tab, "Subscriptions")
        self.tabs.addTab(self.reports_tab, "Reports")
        self.tabs.addTab(self.archive_tab, "Archive")
        
        # Add admin tab with error handling
        try:
            self.tab_admin = AdminTab(get_conn(), self)
            self.tabs.addTab(self.tab_admin, "Admin")
        except Exception as e:
            print("Admin tab error:", e)
            QMessageBox.warning(self, "Admin tab failed to load", str(e))
        
        # Connect signals
        self.subscriptions_tab.rebuilt.connect(self.calendar_tab.rebuild_month_markers)
        
        # Initialize subscription occurrences with 3-month horizon on app launch
        try:
            clear_future_sub_occurrences(self.conn)
            materialize_sub_occurrences(self.conn, horizon_days=90)
        except Exception as e:
            print("Subscription materialization error:", e)
        
        # Initialize automatic subscription sync with modal popups
        try:
            from startup_sync import StartupSyncManager
            self.sync_manager = StartupSyncManager(self)
            self.sync_manager.set_connection(self.conn)
            # Start automatic sync after UI is fully loaded
            self.sync_manager.start_automatic_sync(delay_ms=2000)
        except Exception as e:
            print("Startup sync initialization error:", e)
        
        # Show admin tasks due today popup
        try:
            self._show_admin_tasks_due_today()
        except Exception as e:
            print("Admin popup error:", e)

    def _show_admin_tasks_due_today(self):
        from datetime import date
        today = date.today().strftime("%Y-%m-%d")
        c = self.conn.cursor()
        c.execute("SELECT id,title,COALESCE(notes,'') FROM admin_events WHERE completed=0 AND date(due_dt)=?", (today,))
        rows = c.fetchall()
        if not rows: return
        dlg = QDialog(self); dlg.setWindowTitle("Admin tasks due today")
        v = QVBoxLayout(dlg); v.addWidget(QLabel("These admin tasks are due today:"))
        checks = []
        for r in rows:
            cb = QCheckBox(f"{r[1]}"); cb.setToolTip(r[2]); v.addWidget(cb); checks.append((cb, r[0]))
        btns = QHBoxLayout(); ok = QPushButton("Mark selected completed"); close = QPushButton("Close")
        btns.addWidget(ok); btns.addStretch(1); btns.addWidget(close); v.addLayout(btns)
        close.clicked.connect(dlg.reject)
        def done():
            ids = [tid for (cb, tid) in checks if cb.isChecked()]
            if ids:
                self.conn.execute(f"UPDATE admin_events SET completed=1 WHERE id IN ({','.join(map(str,ids))})")
                self.conn.commit()
            dlg.accept()
        ok.clicked.connect(done); dlg.exec()

    def _apply_dim_dark_theme(self):
        css = """
        QWidget { background: #121417; color: #E9ECF1; font-size: 14px; }
        /* Panels & cards */
        QGroupBox { background: #191C21; border: 1px solid #2A3038; border-radius: 10px; margin-top: 12px; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; color: #E9ECF1; }

        /* Tabs */
        QTabWidget::pane { border: 1px solid #2A3038; border-radius: 10px; background: #191C21; }
        QTabBar::tab {
            padding: 8px 14px; margin: 2px;
            background: #20252C; color: #B3BAC4;
            border: 1px solid #2A3038; border-bottom: none;
            border-top-left-radius: 10px; border-top-right-radius: 10px;
        }
        QTabBar::tab:selected { background: #191C21; color: #E9ECF1; }

        /* Inputs */
        QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDateEdit, QTimeEdit {
            background: #20252C; color: #E9ECF1; border: 1px solid #2A3038; border-radius: 8px; selection-background-color: #2C3F5F;
        }
        QLineEdit:disabled, QComboBox:disabled { color: #8A929C; }
        QAbstractSpinBox::up-button, QAbstractSpinBox::down-button { background: #20252C; border: 0; }

        /* Buttons */
        QPushButton {
            background: #4DA3FF; color: #0B111A; font-weight: 600;
            border: 1px solid #4DA3FF; border-radius: 8px; padding: 6px 12px;
        }
        QPushButton:hover { background: #6BB2FF; border-color: #6BB2FF; }
        QPushButton:disabled { background: #2A3038; color: #8A929C; border-color: #2A3038; }

        /* Tables */
        QTableWidget {
            background: #191C21; gridline-color: #2A3038; alternate-background-color: #20252C;
        }
        QTableWidget::item:selected { background: #26364F; }
        QHeaderView::section {
            background: #20252C; color: #E9ECF1; padding: 6px;
            border: 0; border-right: 1px solid #2A3038;
        }

        /* Calendar (framework widgets) */
        QCalendarWidget QWidget { background: #191C21; color: #E9ECF1; }
        QCalendarWidget QToolButton {
            background: #20252C; color: #E9ECF1; border: 1px solid #2A3038; border-radius: 8px; padding: 4px 8px;
        }
        QCalendarWidget QToolButton:hover { background: #25303A; }
        QCalendarWidget QAbstractItemView {
            selection-background-color: #26364F; selection-color: #E9ECF1;
            outline: 0; background: #191C21; alternate-background-color: #20252C;
        }
        """
        self.setStyleSheet(css)

def main():
    try:
        app = QApplication(sys.argv)
        
        # Set application properties
        app.setApplicationName("Farm Dog Walking App")
        app.setApplicationVersion("1.0")
        app.setOrganizationName("Farm Dog Walking")
        
        # Create and show main window
        window = MainWindow()
        window.show()
        
        # Run the application
        sys.exit(app.exec())
    except Exception as e:
        print(f"App failed to launch: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
