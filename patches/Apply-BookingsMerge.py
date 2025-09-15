import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
app_py = ROOT / "app.py"
helper_import = "from stripe_invoice_bookings import list_invoice_bookings"
src = app_py.read_text(encoding="utf-8")

if helper_import not in src:
    m = re.search(r"^from stripe_integration import .*$", src, flags=re.M)
    if m:
        src = src[:m.end()] + "\n" + helper_import + src[m.end():]
    else:
        src = helper_import + "\n" + src

if "def two_week_window()" not in src:
    fn = '''\nfrom datetime import datetime, date, time, timedelta\n\ndef two_week_window():\n    today = date.today()\n    monday = today - timedelta(days=today.weekday())\n    start_dt = datetime.combine(monday, time.min)\n    end_dt   = start_dt + timedelta(days=14) - timedelta(seconds=1)\n    return start_dt, end_dt\n'''
    src += fn

if "class BookingsTab" in src and "def refresh_two_weeks(" not in src:
    m = re.search(r"class\s+BookingsTab\s*\([^)]+\)\s*:\s*\n", src)
    if m:
        insert = m.end()
        method = '''\n    def refresh_two_weeks(self):\n        try:\n            from dateutil import parser as dtparser\n        except Exception:\n            dtparser = None\n        start_dt, end_dt = two_week_window()\n        start_iso, end_iso = start_dt.isoformat(), end_dt.isoformat()\n        rows, seen = [], set()\n        try:\n            db_rows = self.conn.execute("""\n                SELECT b.id, c.name AS client_name, c.email AS client_email, b.service_type, b.start_dt, b.end_dt,\n                       COALESCE(b.dogs_count,1) AS dogs, COALESCE(b.location,'') AS location, COALESCE(b.status,'') AS status\n                FROM bookings b JOIN clients c ON c.id=b.client_id\n                WHERE b.end_dt >= ? AND b.start_dt <= ? ORDER BY b.start_dt\n            """, (start_iso, end_iso)).fetchall()\n        except Exception:\n            db_rows = []\n        def _val(r,k,d=None):\n            try: return r[k]\n            except Exception: return d\n        for r in db_rows:\n            email = (_val(r,'client_email','') or _val(r,'client_name','')).strip()\n            s, e, svc = _val(r,'start_dt',''), _val(r,'end_dt',''), _val(r,'service_type','')\n            k = (email.lower(), s, e, svc.lower())\n            if k in seen: continue\n            seen.add(k)\n            rows.append({'source':'booking','id':_val(r,'id'), 'client':_val(r,'client_name',''),\n                         'email':_val(r,'client_email',''), 'service':svc,'start_dt':s,'end_dt':e,\n                         'dogs':_val(r,'dogs',1),'location':_val(r,'location',''),'status':_val(r,'status','')})\n        try:\n            sub_rows = self.conn.execute("""\n                SELECT start_dt, end_dt, COALESCE(dogs,1) AS dogs, COALESCE(location,'') AS location\n                FROM sub_occurrences WHERE active=1 AND end_dt >= ? AND start_dt <= ? ORDER BY start_dt\n            """, (start_iso, end_iso)).fetchall()\n        except Exception:\n            sub_rows = []\n        for r in sub_rows:\n            s, e = _val(r,'start_dt',''), _val(r,'end_dt','')\n            k = ('', s, e, 'subscription')\n            if k in seen: continue\n            seen.add(k)\n            rows.append({'source':'subscription','id':None,'client':'(SUB)','email':'','service':'Subscription',\n                         'start_dt':s,'end_dt':e,'dogs':_val(r,'dogs',1),'location':_val(r,'location',''),'status':'active'})\n        try:\n            inv_rows = list_invoice_bookings(days_ahead=14)\n        except Exception:\n            inv_rows = []\n        for r in inv_rows:\n            email = (r.get('client_email') or r.get('client_name') or '').strip()\n            s, e = r.get('start_dt'), r.get('end_dt')\n            if dtparser:\n                try:\n                    s = dtparser.parse(s).isoformat(); e = dtparser.parse(e).isoformat()\n                except Exception: pass\n            svc = r.get('service','')\n            k = (email.lower(), s, e, svc.lower())\n            if k in seen: continue\n            seen.add(k)\n            rows.append({'source':'invoice','id':r.get('stripe_invoice_id'),'client':r.get('client_name') or '',\n                         'email':r.get('client_email') or '','service':svc,'start_dt':s,'end_dt':e,\n                         'dogs':r.get('dogs',1),'location':r.get('location',''),'status':r.get('status','')})\n        if hasattr(self,'_populate_table'): self._populate_table(rows)\n        else:\n            tbl = getattr(self, 'table', None)\n            if tbl is not None:\n                headers = ['ID','Client','Service','Start','End','Location','Dogs','Status','Source']\n                from PySide6.QtWidgets import QTableWidgetItem\n                tbl.setRowCount(0); tbl.setColumnCount(len(headers)); tbl.setHorizontalHeaderLabels(headers)\n                for r in rows:\n                    row = tbl.rowCount(); tbl.insertRow(row)\n                    vals = [r.get('id',''), r.get('client',''), r.get('service',''), r.get('start_dt',''),\n                            r.get('end_dt',''), r.get('location',''), str(r.get('dogs','')), r.get('status',''),\n                            r.get('source','')]\n                    for c,v in enumerate(vals): tbl.setItem(row,c,QTableWidgetItem(str(v)))\n'''
        src = src[:insert] + method + src[insert:]

src = re.sub(r"(\.clicked\.connect\()\s*self\.refresh_services\s*(\))",
             r"\1self.refresh_two_weeks\2", src)

bak = app_py.with_suffix(".py.bak")
if not bak.exists(): bak.write_text(app_py.read_text(encoding="utf-8"), encoding="utf-8")
app_py.write_text(src, encoding="utf-8")
print("Patched app.py; backup saved as app.py.bak")
