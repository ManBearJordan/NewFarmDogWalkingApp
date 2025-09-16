from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PySide6 import QtCore, QtGui, QtWidgets
import os, sys, json
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QTabWidget, QDateTimeEdit, QComboBox, QFileDialog, QSpinBox, QDateEdit, QTimeEdit, QCheckBox, QDialog, QMenu)
from PySide6.QtCore import Qt, QDateTime, QTimer, Signal, QDate, QTime
from PySide6.QtGui import QDesktopServices, QAction, QCursor, QBrush, QColor
from PySide6.QtCore import QUrl
from datetime import datetime, timezone, timedelta, time
from collections import defaultdict

from db import init_db, get_conn, backup_db, clear_future_sub_occurrences, materialize_sub_occurrences, add_booking, booking_items_total_cents
from ics_export import export_bookings
from stripe_integration import (
    list_products, list_recent_invoices, list_subscriptions, open_url,
    ensure_customer, create_invoice_with_item, list_two_week_invoices,
    list_booking_services, create_draft_invoice_for_booking
)
import bookings_two_week as btw
from reports_tab import ReportsTab

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


def ts_to_iso(ts: int) -> str:
    return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%dT%H:%M:%S")


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

        self.table = QTableWidget(0,7)
        self.table.setHorizontalHeaderLabels(["ID","Name","Email","Phone","Address","Notes","StripeCustomerID"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemSelectionChanged.connect(self.on_row_select)
        layout.addWidget(self.table)

        del_btn = QPushButton("Delete selected"); del_btn.clicked.connect(self.delete_client)
        layout.addWidget(del_btn)

        self.refresh()
        
        # Auto-sync customers on load
        try:
            self.sync_customers(show_message=False)
        except Exception:
            # If auto-sync fails, continue without showing error to user
            pass

    def refresh(self):
        rows = self.conn.execute("SELECT id,name,email,phone,address,notes,stripe_customer_id FROM clients ORDER BY id DESC").fetchall()
        self.table.setRowCount(0)
        for r in rows:
            row = self.table.rowCount(); self.table.insertRow(row)
            for i,k in enumerate(["id","name","email","phone","address","notes","stripe_customer_id"]):
                self.table.setItem(row,i,QTableWidgetItem(str(r[k] or "")))

    def on_row_select(self):
        items = self.table.selectedItems()
        if not items: return
        row = items[0].row()
        self.name.setText(self.table.item(row,1).text())
        self.email.setText(self.table.item(row,2).text())
        self.phone.setText(self.table.item(row,3).text())
        self.addr.setText(self.table.item(row,4).text())
        self.notes.setText(self.table.item(row,5).text())

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
        cust_id_item = self.table.item(row,6)
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
    def __init__(self, catalog: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Booking line items")
        self.catalog = catalog
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
            # p["display"] like "Short Walk — Single ($33.00)"
            combo.addItem(p["display"], p)
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

        # Top toolbar with week toggle and refresh
        top_layout = QHBoxLayout()
        self.week_toggle = QComboBox()
        self.week_toggle.addItems(["This week", "Next week"])
        top_layout.addWidget(self.week_toggle)

        self.refresh_btn = QPushButton("Refresh")
        top_layout.addWidget(self.refresh_btn)
        self.refresh_btn.clicked.connect(self.refresh_two_weeks)

        self.import_btn = QPushButton("Import from invoices")
        top_layout.addWidget(self.import_btn)
        self.import_btn.setToolTip('Create/refresh bookings from Stripe invoice metadata')
        self.import_btn.clicked.connect(self.import_from_invoices)
        self.week_toggle.currentIndexChanged.connect(self.refresh_two_weeks)
        
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # Create form widgets
        form = QHBoxLayout()
        self.client_combo = QComboBox()
        self.service = QComboBox()
        self.start_dt = QDateTimeEdit(QtCore.QDateTime.currentDateTime())
        self.end_dt = QDateTimeEdit(QtCore.QDateTime.currentDateTime().addSecs(3600))
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
        
        form.addWidget(QLabel("Client:"))
        form.addWidget(self.client_combo)
        form.addWidget(QLabel("Service:"))
        form.addWidget(self.service)
        form.addWidget(refresh_services_btn)
        form.addWidget(QLabel("Start:"))
        form.addWidget(self.start_dt)
        form.addWidget(QLabel("End:"))
        form.addWidget(self.end_dt)
        form.addWidget(QLabel("Location:"))
        form.addWidget(self.location)
        form.addWidget(QLabel("Dogs:"))
        form.addWidget(self.dogs)
        form.addWidget(QLabel("Price:"))
        form.addWidget(self.price)
        form.addWidget(QLabel("Notes:"))
        form.addWidget(self.notes)
        form.addWidget(add_btn)
        layout.addLayout(form)

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

    def refresh_two_weeks(self):
        which = "this" if self.week_toggle.currentIndex() == 0 else "next"
        start, end = btw.week_window(which)

        db_rows = btw.list_db_bookings(self.conn, start, end)
        sub_rows = btw.list_subscription_holds(self.conn, start, end)
        inv_rows = btw.list_invoice_bookings(start, end)

        all_rows = btw.merge_dedupe(db_rows, sub_rows, inv_rows)
        self._populate_table(all_rows)

    def _populate_table(self, rows):
        self.table.setRowCount(0)
        for r in rows:
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
        except Exception as e:
            QMessageBox.warning(self, "Stripe Error", f"Could not load services: {e}")

    def open_line_items(self):
        try:
            catalog = list_booking_services()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load services: {e}")
            return
        
        dialog = LineItemsDialog(catalog, self)
        if dialog.exec() == QDialog.Accepted:
            self.pending_items = dialog.items

    def add_booking(self):
        idx = self.client_combo.currentIndex()
        if idx < 0:
            QMessageBox.warning(self, "Missing", "Select a client first.")
            return
        
        client_id = self.client_combo.currentData()
        service_data = self.service.currentData()
        service_name = service_data.get("display", "Service") if service_data else self.service.currentText()
        
        start_epoch = _to_epoch(self.start_dt.dateTime())
        end_epoch = _to_epoch(self.end_dt.dateTime())
        location = self.location.text().strip()
        dogs_count = self.dogs.value()
        price_cents = self.price.value()
        notes = self.notes.text().strip()
        
        try:
            booking_id = add_booking(
                self.conn, client_id, service_name, start_epoch, end_epoch,
                location, dogs_count, price_cents, notes, self.pending_items
            )
            self.pending_items = []
            self.refresh_two_weeks()
            QMessageBox.information(self, "Success", f"Booking {booking_id} added.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def import_from_invoices(self):
        try:
            from stripe_invoice_bookings import import_invoice_bookings
            count = import_invoice_bookings()
            self.refresh_two_weeks()
            QMessageBox.information(self, "Import Complete", f"Imported {count} bookings from invoices.")
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

    def open_selected_invoice(self):
        row = self.table.currentRow()
        if row < 0:
            return
        
        # Try to get invoice URL or ID from the booking
        booking_id = self.table.item(row, 0).text()
        try:
            invoice_data = self.conn.execute(
                "SELECT stripe_invoice_id, invoice_url FROM bookings WHERE id=?", 
                (booking_id,)
            ).fetchone()
            
            if invoice_data and invoice_data["invoice_url"]:
                QDesktopServices.openUrl(QUrl(invoice_data["invoice_url"]))
            elif invoice_data and invoice_data["stripe_invoice_id"]:
                from stripe_integration import open_in_stripe
                open_in_stripe("invoice", invoice_data["stripe_invoice_id"])
            else:
                QMessageBox.information(self, "No Invoice", "No invoice linked to this booking.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def delete_booking(self):
        row = self.table.currentRow()
        if row < 0:
            return
        
        booking_id = self.table.item(row, 0).text()
        if QMessageBox.question(self, "Confirm", f"Delete booking {booking_id}?") == QMessageBox.Yes:
            try:
                self.conn.execute("UPDATE bookings SET deleted=1 WHERE id=?", (booking_id,))
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

        # Add refresh button at the top
        button_row = QHBoxLayout()
        self.refresh_calendar_btn = QPushButton("Refresh calendar")
        self.refresh_calendar_btn.clicked.connect(self.refresh_calendar)
        button_row.addWidget(self.refresh_calendar_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        top = QHBoxLayout()
        self.cal = EnhancedCalendarWidget()
        self.cal.setGridVisible(True)
        self.cal.setVerticalHeaderFormat(QtWidgets.QCalendarWidget.NoVerticalHeader)  # ensure hidden
        self.cal.selectionChanged.connect(self.refresh_day)
        top.addWidget(self.cal, 2)
        
        # Legend (accessible)
        legend = QHBoxLayout()
        def _chip(color, text):
            w = QWidget(); w.setFixedHeight(14); w.setStyleSheet(f"background:{color}; border-radius:7px;");
            lbl = QLabel(text); row = QHBoxLayout(); row.setContentsMargins(0,0,0,0); row.setSpacing(6);
            wrap = QWidget(); wrap.setLayout(row); row.addWidget(w); row.addWidget(lbl); return wrap
        for color,label in (("#1a73e8","Bookings"),("#8e24aa","Holds"),("#f57c00","Admin")):
            legend.addWidget(_chip(color,label))
        legend.addStretch(1)
        layout.addLayout(legend)
        
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

    def refresh_calendar(self):
        """
        Refresh calendar functionality:
        1. Pulls subscriptions from Stripe
        2. Drops future holds for cancelled subs with clear_future_sub_occurrences(...)
        3. Re-seeds holds via materialize_sub_occurrences(...)
        4. Refreshes the current day view
        """
        try:
            # Import the required function
            from stripe_integration import list_active_subscriptions
            
            # 1. Pull subscriptions from Stripe
            QMessageBox.information(self, "Refresh Calendar", "Syncing subscriptions from Stripe...")
            subs = list_active_subscriptions()
            
            # Get active subscription IDs
            active_ids = [s.get("id") for s in subs if s.get("id")]
            
            # 2. Find cancelled subscriptions and clear their future holds
            cur = self.conn.cursor()
            cur.execute("SELECT DISTINCT stripe_subscription_id FROM sub_occurrences WHERE start_dt >= date('now')")
            local_ids = [r[0] for r in cur.fetchall()]
            canceled = [sid for sid in local_ids if sid not in active_ids]
            
            if canceled:
                clear_future_sub_occurrences(self.conn, canceled)
                QMessageBox.information(self, "Refresh Calendar", f"Cleared future holds for {len(canceled)} cancelled subscription(s).")
            
            # 3. Re-seed holds for all active subscriptions
            materialize_sub_occurrences(self.conn, horizon_days=14)
            
            # 4. Refresh the current day view
            self.refresh_day()
            
            QMessageBox.information(self, "Refresh Calendar", "Calendar refreshed successfully! Subscriptions synced and holds updated.")
            
        except Exception as e:
            QMessageBox.critical(self, "Refresh Calendar Error", f"Failed to refresh calendar: {str(e)}")

    def compute_subscription_holds_for_day(self, date_str):
        """
        Compute subscription holds for a specific day with proper JOINs
        to get actual client names and service labels (FIXED VERSION)
        """
        try:
            rows = self.conn.execute("""
                SELECT so.start_dt, so.end_dt, so.dogs, so.location, so.notes,
                       so.stripe_subscription_id,
                       ss.days, ss.start_time, ss.end_time,
                       'Subscription' AS service,
                       COALESCE(so.location, 'Subscription') AS client_name
                FROM sub_occurrences so
                LEFT JOIN subs_schedule ss ON ss.stripe_subscription_id = so.stripe_subscription_id
                WHERE so.active=1 AND date(so.start_dt)=?
                ORDER BY so.start_dt
            """, (date_str,)).fetchall()
            
            holds = []
            for row in rows:
                hold = {
                    'start_dt': row['start_dt'],
                    'end_dt': row['end_dt'],
                    'dogs': row['dogs'],
                    'location': row['location'] or '',
                    'notes': row['notes'] or '',
                    'stripe_subscription_id': row['stripe_subscription_id'],
                    'service': row['service'] or 'Subscription',
                    'client_name': row['client_name'] or 'Subscription'
                }
                holds.append(hold)
            
            return holds
            
        except Exception as e:
            print(f"Error computing subscription holds: {e}")
            return []

    def refresh_day(self):
        # Clear table
        self.table.setRowCount(0)

        # Figure out the currently selected date in the grid
        day_dt = self.cal.selectedDate().toPython()
        start_dt = datetime.combine(day_dt, time.min)
        end_dt   = datetime.combine(day_dt, time.max)

        # Pull fresh data
        conn = get_conn()

        # 1) Manual bookings stored in DB
        # Use the correct column names from the database schema
        bookings = conn.execute("""
            SELECT
                id, client_id, start_dt, end_dt, location, dogs_count,
                service_type, notes
            FROM bookings
            WHERE date(start_dt) = ? AND (status IS NULL OR status NOT IN ('cancelled','canceled'))
            ORDER BY start_dt
        """, (day_dt.strftime('%Y-%m-%d'),)).fetchall()

        # 2) Derived subscription holds for that day
        sub_holds = self.compute_subscription_holds_for_day(day_dt.strftime('%Y-%m-%d'))

        # Merge the two lists
        rows = []
        for b in bookings:
            # Convert datetime strings to timestamps for consistency
            try:
                start_ts = int(datetime.fromisoformat(b["start_dt"].replace('Z', '+00:00')).timestamp())
                end_ts = int(datetime.fromisoformat(b["end_dt"].replace('Z', '+00:00')).timestamp())
            except:
                # Fallback if datetime parsing fails
                start_ts = int(start_dt.timestamp())
                end_ts = int(end_dt.timestamp())
            
            rows.append({
                "src": "booking",
                "client_id": b["client_id"],
                "start_ts": start_ts,
                "end_ts": end_ts,
                "location": b["location"] or "",
                "dogs": b["dogs_count"] or 1,
                "service_code": b["service_type"] or "",
                "service_name": b["service_type"] or "",
            })
        
        for h in (sub_holds or []):
            rows.append({
                "src": "sub",
                "client_id": None,
                "start_ts": int(datetime.fromisoformat(h["start_dt"]).timestamp()) if h.get("start_dt") else 0,
                "end_ts": int(datetime.fromisoformat(h["end_dt"]).timestamp()) if h.get("end_dt") else 0,
                "location": h.get("location",""),
                "dogs": h.get("dogs", 1),
                "service_code": "",
                "service_name": h.get("service", "Subscription"),
            })

        # Populate the table
        for r in rows:
            client_name, address, pets_csv = get_client_bundle(conn, r.get("client_id"), r.get("location",""))

            # Service label: prefer stored label, else map from code
            svc = (r.get("service_name") or "").strip()
            if not svc:
                svc = friendly_service_label(r.get("service_code"))

            i = self.table.rowCount()
            self.table.insertRow(i)

            self.table.setItem(i, 0, QTableWidgetItem(ts_to_iso(r["start_ts"])))  # Start
            self.table.setItem(i, 1, QTableWidgetItem(ts_to_iso(r["end_ts"])))    # End
            self.table.setItem(i, 2, QTableWidgetItem(client_name or ""))         # Client
            self.table.setItem(i, 3, QTableWidgetItem(address or ""))             # Address
            self.table.setItem(i, 4, QTableWidgetItem(svc))                        # Service
            self.table.setItem(i, 5, QTableWidgetItem(pets_csv or ""))            # Pets

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
        self.refresh_btn = QPushButton("Refresh from Stripe")
        self.refresh_btn.clicked.connect(self.refresh_from_stripe)
        self.save_btn = QPushButton("Save Schedule for Selected")
        self.save_btn.clicked.connect(self.save_schedule)
        self.rebuild_btn = QPushButton("Rebuild next 2 weeks")
        self.rebuild_btn.clicked.connect(self.rebuild_occurrences)
        top.addWidget(self.refresh_btn); top.addWidget(self.save_btn); top.addWidget(self.rebuild_btn)
        layout.addLayout(top)

        editor = QHBoxLayout()
        editor.addWidget(QLabel("Days:"))
        self.days = DaysPicker()
        editor.addWidget(self.days)
        self.start_time = QTimeEdit(); self.start_time.setDisplayFormat("HH:mm"); self.start_time.setTime(QtCore.QTime(9,0))
        self.start_time.setFixedWidth(80)
        self.end_time   = QTimeEdit(); self.end_time.setDisplayFormat("HH:mm");   self.end_time.setTime(QtCore.QTime(10,0))
        self.end_time.setFixedWidth(80)
        self.dogs = QSpinBox(); self.dogs.setRange(1,20); self.dogs.setValue(1)
        self.dogs.setFixedWidth(60)
        self.loc = QLineEdit(); self.loc.setPlaceholderText("Location")
        self.notes = QLineEdit(); self.notes.setPlaceholderText("Notes")
        for w,label in [(self.start_time,"Start"),(self.end_time,"End"),(self.dogs,"Dogs"),(self.loc,"Location"),(self.notes,"Notes")]:
            editor.addWidget(QLabel(label+":"))
            editor.addWidget(w)
        layout.addLayout(editor)

        self.table = QTableWidget(0,8)
        self.table.setHorizontalHeaderLabels(["ID","Customer","Status","Products","Days","Time","Dogs","Location"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemSelectionChanged.connect(self.on_row_select)
        layout.addWidget(self.table)

        self.refresh_from_stripe()

    def on_row_select(self):
        items = self.table.selectedItems()
        if not items: return
        row = items[0].row()
        sub_id = self.table.item(row,0).text()
        # Load schedule if exists
        sched = self.conn.execute("SELECT * FROM subs_schedule WHERE stripe_subscription_id=?", (sub_id,)).fetchone()
        if sched:
            self.days.set_days(sched["days"] or "")
            self.start_time.setTime(QtCore.QTime.fromString(sched["start_time"] or "09:00", "HH:mm"))
            self.end_time.setTime(QtCore.QTime.fromString(sched["end_time"] or "10:00", "HH:mm"))
            self.dogs.setValue(int(sched["dogs"] or 1))
            self.loc.setText(sched["location"] or "")
            self.notes.setText(sched["notes"] or "")

    def save_schedule(self):
        items = self.table.selectedItems()
        if not items: return
        row = items[0].row()
        sub_id = self.table.item(row,0).text()
        days = self.days.get_days_csv()
        start_time = self.start_time.time().toString("HH:mm")
        end_time = self.end_time.time().toString("HH:mm")
        dogs = self.dogs.value()
        location = self.loc.text().strip()
        notes = self.notes.text().strip()
        
        self.conn.execute("""
        INSERT OR REPLACE INTO subs_schedule(stripe_subscription_id,days,start_time,end_time,dogs,location,notes)
        VALUES(?,?,?,?,?,?,?)
        """, (sub_id,days,start_time,end_time,dogs,location,notes))
        self.conn.commit()
        QMessageBox.information(self,"Saved",f"Schedule saved for subscription {sub_id}")

    def rebuild_occurrences(self):
        try:
            materialize_sub_occurrences(self.conn, horizon_days=14)
            self.rebuilt.emit()
            QMessageBox.information(self,"Rebuilt","Subscription occurrences rebuilt for next 2 weeks")
        except Exception as e:
            QMessageBox.critical(self,"Error",str(e))

    def refresh_from_stripe(self):
        try:
            subs = list_subscriptions()
            self.table.setRowCount(0)
            for s in subs:
                row = self.table.rowCount(); self.table.insertRow(row)
                self.table.setItem(row,0,QTableWidgetItem(s.get("id","")))
                self.table.setItem(row,1,QTableWidgetItem(s.get("customer_name","")))
                self.table.setItem(row,2,QTableWidgetItem(s.get("status","")))
                self.table.setItem(row,3,QTableWidgetItem(s.get("products","")))
                self.table.setItem(row,4,QTableWidgetItem(""))  # Days - filled from schedule
                self.table.setItem(row,5,QTableWidgetItem(""))  # Time - filled from schedule
                self.table.setItem(row,6,QTableWidgetItem(""))  # Dogs - filled from schedule
                self.table.setItem(row,7,QTableWidgetItem(""))  # Location - filled from schedule
        except Exception as e:
            QMessageBox.critical(self,"Stripe Error",str(e))

# ---------------- Main Window ----------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Farm Dog Walking App")
        self.setGeometry(100, 100, 1400, 900)
        
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
        self.clients_tab = ClientsTab()
        self.pets_tab = PetsTab()
        self.bookings_tab = BookingsTab()
        self.calendar_tab = CalendarTab()
        self.subscriptions_tab = SubscriptionsTab()
        self.reports_tab = ReportsTab()
        
        self.tabs.addTab(self.clients_tab, "Clients")
        self.tabs.addTab(self.pets_tab, "Pets")
        self.tabs.addTab(self.bookings_tab, "Bookings")
        self.tabs.addTab(self.calendar_tab, "Calendar")
        self.tabs.addTab(self.subscriptions_tab, "Subscriptions")
        self.tabs.addTab(self.reports_tab, "Reports")
        
        # Connect signals
        self.subscriptions_tab.rebuilt.connect(self.calendar_tab.rebuild_month_markers)

def main():
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

if __name__ == "__main__":
    main()
