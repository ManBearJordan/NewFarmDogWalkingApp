# reports_tab.py
from __future__ import annotations
import os, sqlite3, math, time
from datetime import datetime, timedelta
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QDateEdit,
    QPushButton, QTextBrowser, QFileDialog, QTableWidget, QTableWidgetItem, QLabel
)
from PySide6.QtPrintSupport import QPrinter

# local imports (your modules)
import stripe_integration as si
from db import get_conn

class ReportsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)

        # ---------- Run Sheet ----------
        rs_box = QGroupBox("Run Sheet")
        rs_lay = QVBoxLayout(rs_box)

        top = QHBoxLayout()
        self.date_edit = QDateEdit(calendarPopup=True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        top.addWidget(QLabel("Date:"))
        top.addWidget(self.date_edit, 0)
        top.addStretch(1)

        btns = QHBoxLayout()
        self.btn_preview = QPushButton("Preview")
        self.btn_pdf = QPushButton("Save PDF…")
        btns.addWidget(self.btn_preview)
        btns.addWidget(self.btn_pdf)
        btns.addStretch(1)

        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        self.preview.setMinimumHeight(260)

        rs_lay.addLayout(top)
        rs_lay.addLayout(btns)
        rs_lay.addWidget(self.preview)

        # ---------- Outstanding ----------
        oi_box = QGroupBox("Outstanding Invoices (open / uncollectible)")
        oi_lay = QVBoxLayout(oi_box)

        oi_btns = QHBoxLayout()
        self.btn_oi_refresh = QPushButton("Refresh")
        self.lbl_oi_count = QLabel("")
        oi_btns.addWidget(self.btn_oi_refresh)
        oi_btns.addStretch(1)
        oi_btns.addWidget(self.lbl_oi_count)

        self.tbl_oi = QTableWidget(0, 7)
        self.tbl_oi.setHorizontalHeaderLabels(["Date", "Status", "Customer", "Email", "Total", "Invoice ID", "Actions"])
        self.tbl_oi.horizontalHeader().setStretchLastSection(True)
        self.tbl_oi.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_oi.setEditTriggers(QTableWidget.NoEditTriggers)

        oi_lay.addLayout(oi_btns)
        oi_lay.addWidget(self.tbl_oi)

        # ---------- Subscription Logs ----------
        logs_box = QGroupBox("Subscription Operations Log")
        logs_lay = QVBoxLayout(logs_box)

        logs_btns = QHBoxLayout()
        self.btn_download_log = QPushButton("Download Full Log")
        self.btn_download_log.setStyleSheet("QPushButton { background-color: #007bff; color: white; font-weight: bold; }")
        self.lbl_log_info = QLabel("Download the complete subscription operations log (subscription_logs.txt)")
        self.lbl_log_info.setStyleSheet("QLabel { color: #666; font-style: italic; }")
        logs_btns.addWidget(self.btn_download_log)
        logs_btns.addStretch(1)
        logs_btns.addWidget(self.lbl_log_info)

        logs_lay.addLayout(logs_btns)

        lay.addWidget(rs_box)
        lay.addWidget(oi_box)
        lay.addWidget(logs_box)
        lay.addStretch(1)

        # wiring
        self.btn_preview.clicked.connect(self._do_preview)
        self.btn_pdf.clicked.connect(self._save_pdf)
        self.btn_oi_refresh.clicked.connect(self._refresh_oi)
        self.btn_download_log.clicked.connect(self._download_subscription_log)

    # ----------------- Run Sheet -----------------
    def _do_preview(self):
        dt = self.date_edit.date().toPython()  # datetime.date
        rows = self._fetch_bookings_for_date(dt)
        html = self._render_runsheet_html(dt, rows)
        self.preview.setHtml(html)

    def _save_pdf(self):
        # ensure preview is up-to-date
        if not self.preview.toPlainText().strip():
            self._do_preview()
        path, _ = QFileDialog.getSaveFileName(self, "Save Run Sheet PDF", f"RunSheet_{self.date_edit.text()}.pdf", "PDF Files (*.pdf)")
        if not path:
            return
        doc = QTextDocument()
        doc.setHtml(self.preview.toHtml())
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        doc.print_(printer)

    def _fetch_bookings_for_date(self, date_obj):
        """
        Defensive fetch:
        1) try db module helpers if present;
        2) fallback to sqlite with common column names.
        Returns a list of dicts with keys: time_str, client, pets, service, notes, location
        """
        # try via db module
        try:
            import db
            # try common function names
            for fn in (
                "get_bookings_for_date", "get_bookings_on_date", "list_bookings_for_date",
                "get_bookings_in_range", "list_bookings_in_range",
            ):
                if hasattr(db, fn):
                    start = datetime(date_obj.year, date_obj.month, date_obj.day)
                    end = start + timedelta(days=1)
                    if "range" in fn:
                        return self._normalize_rows(getattr(db, fn)(start, end))
                    else:
                        return self._normalize_rows(getattr(db, fn)(date_obj))
        except Exception:
            pass

        # sqlite fallback
        rows = []
        start = datetime(date_obj.year, date_obj.month, date_obj.day)
        end = start + timedelta(days=1)
        start_ts = int(start.timestamp())
        end_ts = int(end.timestamp())

        with get_conn() as conn:
            c = conn.cursor()
            # discover columns
            c.execute("PRAGMA table_info(bookings)")
            cols = [r[1] for r in c.fetchall()]
            # best-effort column mapping
            col_start = next((n for n in cols if n in ("start_utc","start_ts","start","start_time")), None)
            col_end   = next((n for n in cols if n in ("end_utc","end_ts","end","end_time")), None)
            col_name  = next((n for n in cols if n in ("client_name","name","customer_name")), None)
            col_srv   = next((n for n in cols if n in ("service_label","service","service_code")), None)
            col_loc   = next((n for n in cols if n in ("location","address","where")), None)
            col_notes = next((n for n in cols if n in ("notes","note","details")), None)
            col_pets  = next((n for n in cols if n in ("pets","pet_names","pet")), None)

            if not col_start or not col_end:
                return rows

            q = f"""
                SELECT {col_start}, {col_end},
                       {col_name if col_name else "''"},
                       {col_srv if col_srv else "''"},
                       {col_loc if col_loc else "''"},
                       {col_notes if col_notes else "''"},
                       {col_pets if col_pets else "''"}
                FROM bookings
                WHERE {col_start} >= ? AND {col_start} < ?
                ORDER BY {col_start} ASC
            """
            for r in c.execute(q, (start_ts, end_ts)):
                st, en, nm, srv, loc, notes, pets = r
                rows.append({
                    "start_ts": st, "end_ts": en,
                    "client": nm or "",
                    "service": srv or "",
                    "location": loc or "",
                    "notes": notes or "",
                    "pets": pets or "",
                })
        return self._normalize_rows(rows)

    def _normalize_rows(self, rows):
        out = []
        for r in rows or []:
            # try several shapes
            st = r.get("start_ts") or r.get("start_utc") or r.get("start") or r.get("start_time")
            en = r.get("end_ts") or r.get("end_utc") or r.get("end") or r.get("end_time")
            if isinstance(st, str) and st.isdigit(): st = int(st)
            if isinstance(en, str) and en.isdigit(): en = int(en)
            try:
                start_dt = datetime.fromtimestamp(int(st))
                end_dt = datetime.fromtimestamp(int(en))
            except Exception:
                # last resort: skip unparsable row
                continue
            tstr = f"{start_dt:%I:%M %p} – {end_dt:%I:%M %p}".lstrip("0")
            out.append({
                "time_str": tstr,
                "client": r.get("client") or r.get("client_name") or r.get("customer_name") or "",
                "service": r.get("service") or r.get("service_label") or r.get("service_code") or "",
                "location": r.get("location") or "",
                "pets": r.get("pets") or r.get("pet_names") or "",
                "notes": r.get("notes") or "",
            })
        return out

    def _render_runsheet_html(self, date_obj, rows):
        title = f"Run Sheet — {date_obj:%A, %d %b %Y}"
        head = """
        <style>
        body { font-family: Arial, sans-serif; }
        h1 { margin: 0 0 12px 0; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #ddd; padding: 6px 8px; font-size: 12px; }
        th { background: #f5f5f5; text-align: left; }
        .time { width: 110px; white-space: nowrap; }
        .svc  { width: 160px; }
        .loc  { width: 200px; }
        </style>
        """
        rows_html = ""
        for r in rows:
            rows_html += (
                f"<tr>"
                f"<td class='time'>{r['time_str']}</td>"
                f"<td>{self._esc(r['client'])}</td>"
                f"<td class='svc'>{self._esc(r['service'])}</td>"
                f"<td class='loc'>{self._esc(r['location'])}</td>"
                f"<td>{self._esc(r['pets'])}</td>"
                f"<td>{self._esc(r['notes'])}</td>"
                f"</tr>"
            )
        if not rows_html:
            rows_html = "<tr><td colspan='6'><em>No bookings found for this day.</em></td></tr>"

        return f"""
        {head}
        <h1>{title}</h1>
        <table>
          <thead>
            <tr>
              <th>Time</th><th>Client</th><th>Service</th><th>Location</th><th>Pets</th><th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
        """

    @staticmethod
    def _esc(s):
        return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

    # ----------------- Outstanding Invoices -----------------
    def _refresh_oi(self):
        items = si.list_outstanding_invoices()
        items.sort(key=lambda x: x.get("created") or 0, reverse=True)
        self.tbl_oi.setRowCount(len(items))
        for row, it in enumerate(items):
            dt_str = datetime.fromtimestamp(int(it["created"] or 0)).strftime("%Y-%m-%d")
            total = it.get("total") or 0
            money = f"${total/100:.2f} {(it.get('currency') or 'aud').upper()}"
            self.tbl_oi.setItem(row, 0, QTableWidgetItem(dt_str))
            self.tbl_oi.setItem(row, 1, QTableWidgetItem(it.get("status") or ""))
            self.tbl_oi.setItem(row, 2, QTableWidgetItem(it.get("customer_name") or ""))
            self.tbl_oi.setItem(row, 3, QTableWidgetItem(it.get("customer_email") or ""))
            self.tbl_oi.setItem(row, 4, QTableWidgetItem(money))
            self.tbl_oi.setItem(row, 5, QTableWidgetItem(it.get("id") or ""))

            # Actions
            w = QWidget()
            h = QHBoxLayout(w); h.setContentsMargins(0,0,0,0)
            b1 = QPushButton("Open invoice")
            b2 = QPushButton("Open customer")
            inv_id = it.get("id"); cust_id = it.get("customer_id")
            b1.clicked.connect(lambda _=None, iid=inv_id: si.open_in_stripe("invoice", iid))
            if cust_id:
                b2.clicked.connect(lambda _=None, cid=cust_id: si.open_in_stripe("customer", cid))
            else:
                b2.setEnabled(False)
            h.addWidget(b1); h.addWidget(b2); h.addStretch(1)
            self.tbl_oi.setCellWidget(row, 6, w)

        self.tbl_oi.resizeColumnsToContents()
        self.lbl_oi_count.setText(f"{len(items)} shown")

    # ----------------- Subscription Log Download -----------------
    def _download_subscription_log(self):
        """Download the complete subscription operations log file."""
        import os
        from datetime import datetime
        
        log_file_path = "subscription_logs.txt"
        
        # Check if log file exists
        if not os.path.exists(log_file_path):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, 
                "Log File Not Found", 
                f"The subscription log file '{log_file_path}' does not exist.\n\n"
                "This may mean no subscription operations have been logged yet."
            )
            return
        
        # Generate default filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"subscription_logs_{timestamp}.txt"
        
        # Open file dialog to save the log
        path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Subscription Log", 
            default_filename, 
            "Text Files (*.txt);;All Files (*)"
        )
        
        if not path:
            return  # User cancelled
        
        try:
            # Copy the log file to the selected location
            import shutil
            shutil.copy2(log_file_path, path)
            
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "Log Downloaded",
                f"✅ Subscription log downloaded successfully to:\n{path}"
            )
            
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Download Error", 
                f"Failed to download log file: {e}"
            )
