\
import os, sqlite3, datetime, pathlib
from datetime import timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    ensure_admin_events_schema(conn)    # safety net
    return conn

def ensure_admin_events_schema(conn):
    cur = conn.cursor()

    # Create table if missing (use your real column names)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          due_dt TEXT NOT NULL,          -- << your schema uses due_dt
          recurrence TEXT,
          notes TEXT,
          dogs_count INTEGER DEFAULT 1,
          completed INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Backward-compat: if you ever had 'due_date', migrate to 'due_dt'
    cur.execute("PRAGMA table_info(admin_events)")
    cols = {row[1] for row in cur.fetchall()}

    if "due_dt" not in cols and "due_date" in cols:
        cur.execute("ALTER TABLE admin_events ADD COLUMN due_dt TEXT")
        # copy values from legacy column
        cur.execute("UPDATE admin_events SET due_dt = due_date WHERE due_dt IS NULL OR due_dt = ''")

    if "completed" not in cols:
        cur.execute("ALTER TABLE admin_events ADD COLUMN completed INTEGER NOT NULL DEFAULT 0")

    conn.commit()

def add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, sql_type: str, default_clause: str = ""):
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type} {default_clause}".strip())
        conn.commit()

def ensure_column(conn, table: str, column: str, decl: str):
    """Helper to safely add a column if it doesn't exist"""
    cur = conn.cursor()
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})")]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        conn.commit()

def ensure_index(conn, index_name: str, create_sql: str):
    """Helper to safely create an index if it doesn't exist"""
    try:
        conn.execute(create_sql)
        conn.commit()
    except sqlite3.OperationalError:
        # Index might already exist
        pass

def ensure_credit_schema(conn):
    """Ensure credit and subscription booking schema is in place"""
    cur = conn.cursor()
    # Add credit_cents column if missing
    cur.execute("PRAGMA table_info(clients)")
    cols = {r[1] for r in cur.fetchall()}
    if "credit_cents" not in cols:
        cur.execute("ALTER TABLE clients ADD COLUMN credit_cents INTEGER NOT NULL DEFAULT 0")
    
    # Add created_from_sub_id, source columns to bookings
    cur.execute("PRAGMA table_info(bookings)")
    cols = {r[1] for r in cur.fetchall()}
    if "created_from_sub_id" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN created_from_sub_id TEXT")
    if "source" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN source TEXT DEFAULT 'manual'")
    
    # Index to avoid duplicate subscription bookings
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_bookings_sub_start
        ON bookings(created_from_sub_id, start_dt)
        WHERE created_from_sub_id IS NOT NULL
    """)
    conn.commit()

def ensure_credit_column(conn):
    """Add credit_cents column to clients table if it doesn't exist"""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(clients)")
    cols = [c[1] for c in cur.fetchall()]
    if "credit_cents" not in cols:
        cur.execute("ALTER TABLE clients ADD COLUMN credit_cents INTEGER NOT NULL DEFAULT 0")
    conn.commit()

def get_client_credit(conn, client_id):
    """Get the current credit balance for a client in cents"""
    row = conn.execute("SELECT credit_cents FROM clients WHERE id=?", (client_id,)).fetchone()
    return (row["credit_cents"] or 0) if row else 0

def add_client_credit(conn, client_id, amount_cents):
    """Add credit to a client's balance"""
    conn.execute("UPDATE clients SET credit_cents = credit_cents + ? WHERE id=?", (amount_cents, client_id))
    conn.commit()

def use_client_credit(conn, client_id, amount_cents):
    """Use client credit, returning the amount actually used"""
    cur = conn.cursor()
    cur.execute("SELECT credit_cents FROM clients WHERE id=?", (client_id,))
    row = cur.fetchone()
    available = row["credit_cents"] if row else 0
    to_use = min(available, amount_cents)
    cur.execute("UPDATE clients SET credit_cents = credit_cents - ? WHERE id=?", (to_use, client_id))
    conn.commit()
    return to_use

def ensure_schema_upgrades(conn):
    cur = conn.cursor()

    # bookings: link to invoice (if not already present)
    cur.execute("PRAGMA table_info(bookings)")
    cols = {r[1] for r in cur.fetchall()}
    if "stripe_invoice_id" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN stripe_invoice_id TEXT")
    if "invoice_url" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN invoice_url TEXT")
    if "status" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN status TEXT DEFAULT 'scheduled'")
    if "service" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN service TEXT")  # alias for service_type if you use both
    if "stripe_price_id" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN stripe_price_id TEXT")  # new
    
    # Add canonical start/end columns (without _dt suffix)
    if "start" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN start TEXT")
        # Copy existing start_dt values to start
        cur.execute("UPDATE bookings SET start = start_dt WHERE start IS NULL")
    if "end" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN end TEXT")
        # Copy existing end_dt values to end
        cur.execute("UPDATE bookings SET end = end_dt WHERE end IS NULL")
    if "dogs" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN dogs INTEGER DEFAULT 1")
        # Copy existing dogs_count values to dogs
        cur.execute("UPDATE bookings SET dogs = dogs_count WHERE dogs IS NULL")
    if "service_name" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN service_name TEXT")
        # Copy existing service values to service_name
        cur.execute("UPDATE bookings SET service_name = COALESCE(service, service_type) WHERE service_name IS NULL")
    if "updated_at" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN updated_at TEXT")

    # sub_occurrences: remember if a booking was created
    cur.execute("PRAGMA table_info(sub_occurrences)")
    cols = {r[1] for r in cur.fetchall()}
    if "booking_id" not in cols:
        cur.execute("ALTER TABLE sub_occurrences ADD COLUMN booking_id INTEGER")

    # (Optional) de-dupe: same client+service+window is unique
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_booking_dedupe
        ON bookings(client_id, service_type, start, end)
    """)
    conn.commit()

def migrate_bookings(conn: sqlite3.Connection):
    # Needed by Calendar earlier and by this feature
    add_column_if_missing(conn, "bookings", "dogs_count", "INTEGER", "DEFAULT 1")
    add_column_if_missing(conn, "bookings", "stripe_invoice_id", "TEXT")
    add_column_if_missing(conn, "bookings", "invoice_url", "TEXT")
    add_column_if_missing(conn, "bookings", "source", "TEXT", "DEFAULT 'manual'")
    add_column_if_missing(conn, "bookings", "service", "TEXT")
    add_column_if_missing(conn, "bookings", "start_utc", "INTEGER")
    add_column_if_missing(conn, "bookings", "end_utc", "INTEGER")
    add_column_if_missing(conn, "bookings", "deleted", "INTEGER", "DEFAULT 0")
    # Optional: help de-dupe quickly
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_booking_dedupe
        ON bookings(client_id, service, start_utc, end_utc);
    """)
    conn.commit()

def _migrate_invoices_booking_nullable(conn):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(invoices)")
    cols = cur.fetchall()
    if not cols:
        return
    info = {c["name"]: c for c in cols}
    if "booking_id" in info and info["booking_id"]["notnull"] == 1:
        # backup
        p = pathlib.Path(DB_PATH)
        backups = p.parent / "backups"
        backups.mkdir(exist_ok=True)
        (backups / f"pre-migrate-invoices-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.db").write_bytes(p.read_bytes())
        # create new table with nullable booking_id and uniqueness on stripe_invoice_id
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS invoices_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id INTEGER REFERENCES bookings(id) ON DELETE SET NULL,
                stripe_invoice_id TEXT UNIQUE,
                customer_name TEXT,
                customer_email TEXT,
                status TEXT,
                total_cents INTEGER,
            stripe_created INTEGER,
                url TEXT,
            stripe_mode TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # copy across
        try:
            rows = cur.execute("SELECT booking_id, stripe_invoice_id, customer_name, customer_email, status, total_cents, url, created_at FROM invoices").fetchall()
            for r in rows:
                cur.execute("""INSERT OR IGNORE INTO invoices_new(booking_id,stripe_invoice_id,customer_name,customer_email,status,total_cents,url,created_at)
                               VALUES(?,?,?,?,?,?,?,?)""",
                            (r["booking_id"], r["stripe_invoice_id"], r["customer_name"], r["customer_email"],
                             r["status"], r["total_cents"], r["url"], r["created_at"]))
        except Exception:
            pass
        cur.executescript("""
            DROP TABLE invoices;
            ALTER TABLE invoices_new RENAME TO invoices;
        """)
        conn.commit()

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript(
        """
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            address TEXT,
            stripe_customer_id TEXT,
            notes TEXT,
            dogs_count INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS pets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            species TEXT DEFAULT 'dog',
            breed TEXT,
            dob TEXT,
            meds TEXT,
            behaviour TEXT
        );
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            service_type TEXT NOT NULL,
            start_dt TEXT NOT NULL,
            end_dt TEXT NOT NULL,
            location TEXT,
            status TEXT DEFAULT 'scheduled',
            price_cents INTEGER DEFAULT 0,
            notes TEXT,
            dogs_count INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS booking_pets (
            booking_id INTEGER REFERENCES bookings(id) ON DELETE CASCADE,
            pet_id INTEGER REFERENCES pets(id) ON DELETE CASCADE,
            PRIMARY KEY (booking_id, pet_id)
        );
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER REFERENCES bookings(id) ON DELETE SET NULL,
            stripe_invoice_id TEXT UNIQUE,
            customer_name TEXT,
            customer_email TEXT,
            status TEXT,
            total_cents INTEGER,
            stripe_created INTEGER,
            url TEXT,
            stripe_mode TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS admin_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            due_dt TEXT NOT NULL,
            recurrence TEXT,
            notes TEXT,
            dogs_count INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS booking_items (
            id INTEGER PRIMARY KEY,
            booking_id INTEGER NOT NULL,
            stripe_price_id TEXT NOT NULL,
            service_name TEXT NOT NULL,
            qty INTEGER NOT NULL DEFAULT 1,
            unit_amount_cents INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(booking_id) REFERENCES bookings(id) ON DELETE CASCADE
        );
        """
    )
    try:
        _migrate_invoices_booking_nullable(conn)
    except Exception:
        pass
    
    # add stripe_created if missing
    try:
        c.execute("ALTER TABLE invoices ADD COLUMN stripe_created INTEGER")
        conn.commit()
    except Exception:
        pass
    
    conn.commit()
    migrate_bookings(conn)
    migrate_subs_tables(conn)
    ensure_schema_upgrades(conn)
    ensure_admin_events_schema(conn)    # <-- add this line
    ensure_credit_schema(conn)  # Add credit and subscription booking schema
    
    # --- gentle migrations ---
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(bookings)")
    cols = {r[1] for r in cur.fetchall()}
    if "google_event_id" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN google_event_id TEXT")
    if "invoice_url" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN invoice_url TEXT")
    
    # Add stripeCustomerId column to clients table for camelCase compatibility
    ensure_column(conn, "clients", "stripeCustomerId", "TEXT")
    ensure_index(conn, "idx_clients_stripeCustomerId",
                 "CREATE INDEX IF NOT EXISTS idx_clients_stripeCustomerId ON clients(stripeCustomerId)")
    
    # Add performance indexes
    ensure_index(conn, "idx_bookings_start", "CREATE INDEX IF NOT EXISTS idx_bookings_start ON bookings(start)")
    ensure_index(conn, "idx_sub_occ_start", "CREATE INDEX IF NOT EXISTS idx_sub_occ_start ON sub_occurrences(occ_date)")
    
    conn.commit()
    conn.close()

def backup_db():
    p = pathlib.Path(DB_PATH)
    if not p.exists():
        return
    backups = pathlib.Path(os.path.dirname(DB_PATH), "backups")
    backups.mkdir(exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    (backups / f"app-{ts}.db").write_bytes(p.read_bytes())


# ---- Subscriptions tables & helpers ----
def migrate_subs_tables(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS subs_schedule(
            stripe_subscription_id TEXT PRIMARY KEY,
            days TEXT,
            start_time TEXT,
            end_time   TEXT,
            dogs       INTEGER DEFAULT 1,
            location   TEXT,
            notes      TEXT,
            updated_at TEXT
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sub_occurrences(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stripe_subscription_id TEXT,
            start_dt TEXT,
            end_dt   TEXT,
            dogs     INTEGER,
            location TEXT,
            notes    TEXT,
            week_start TEXT,
            active   INTEGER DEFAULT 1
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS subs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
            service_name TEXT,
            mon INTEGER DEFAULT 0,
            tue INTEGER DEFAULT 0,
            wed INTEGER DEFAULT 0,
            thu INTEGER DEFAULT 0,
            fri INTEGER DEFAULT 0,
            sat INTEGER DEFAULT 0,
            sun INTEGER DEFAULT 0,
            start_min INTEGER DEFAULT 540,
            end_min INTEGER DEFAULT 600,
            dogs INTEGER DEFAULT 1,
            location TEXT,
            status TEXT DEFAULT 'active'
        );
    """)
    conn.commit()

def clear_future_sub_occurrences(conn, subscription_ids=None, from_iso=None):
    import datetime
    cur = conn.cursor()
    if from_iso is None:
        from_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat()
    if subscription_ids:
        qmarks = ",".join(["?"] * len(subscription_ids))
        cur.execute(f"""
            DELETE FROM sub_occurrences
            WHERE start_dt >= ? AND stripe_subscription_id IN ({qmarks})
        """, (from_iso, *subscription_ids))
    else:
        cur.execute("""
            DELETE FROM sub_occurrences
            WHERE start_dt >= ?
        """, (from_iso,))
    conn.commit()

def materialize_sub_occurrences(conn, horizon_days=14, tz="local"):
    import datetime
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT stripe_subscription_id, days, start_time, end_time, dogs, location, notes
        FROM subs_schedule
    """).fetchall()
    if not rows:
        return
    today = datetime.date.today()
    horizon = today + datetime.timedelta(days=horizon_days)
    dow = {"MON":0,"TUE":1,"WED":2,"THU":3,"FRI":4,"SAT":5,"SUN":6}
    for r in rows:
        # sqlite row can be tuple or dict-like
        sid = r["stripe_subscription_id"] if isinstance(r, dict) else r[0]
        days = (r["days"] if isinstance(r, dict) else r[1]) or ""
        start_time = (r["start_time"] if isinstance(r, dict) else r[2]) or "09:00"
        end_time   = (r["end_time"]   if isinstance(r, dict) else r[3]) or "10:00"
        dogs       = int((r["dogs"]    if isinstance(r, dict) else r[4]) or 1)
        location   = (r["location"]    if isinstance(r, dict) else r[5]) or ""
        notes      = (r["notes"]       if isinstance(r, dict) else r[6]) or ""
        dset = [d.strip().upper() for d in days.split(",") if d.strip()]
        dow_nums = [dow[d] for d in dset if d in dow]
        if not dow_nums:
            continue
        d = today
        while d < horizon:
            if d.weekday() in dow_nums:
                st_iso = datetime.datetime.combine(d, datetime.time.fromisoformat(start_time)).isoformat()
                en_iso = datetime.datetime.combine(d, datetime.time.fromisoformat(end_time)).isoformat()
                exists = cur.execute("""
                    SELECT 1 FROM sub_occurrences
                    WHERE stripe_subscription_id=? AND start_dt=? AND end_dt=? LIMIT 1
                """, (sid, st_iso, en_iso)).fetchone()
                if not exists:
                    week_start = (d - datetime.timedelta(days=d.weekday())).isoformat()
                    cur.execute("""
                        INSERT INTO sub_occurrences(stripe_subscription_id,start_dt,end_dt,dogs,location,notes,week_start,active)
                        VALUES (?,?,?,?,?,?,?,1)
                    """, (sid, st_iso, en_iso, dogs, location, notes, week_start))
            d += datetime.timedelta(days=1)
    conn.commit()

def add_booking(conn, client_id, service_code, start_dt, end_dt,
                location, dogs, price_cents, notes, pending_items=None,
                stripe_invoice_id=None, invoice_url=None, status="scheduled", 
                stripe_price_id=None):
    cur = conn.cursor()
    
    # start_dt and end_dt are now expected to be ISO strings from QDateTime formatting
    # No conversion needed - use them directly
    
    cur.execute(
        """
        INSERT INTO bookings
          (client_id, service_type, start_dt, end_dt, start, end, location, dogs_count, dogs, price_cents,
           notes, stripe_invoice_id, invoice_url, status, service_name, stripe_price_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            client_id, service_code, start_dt, end_dt, start_dt, end_dt, location or "",
            int(dogs or 1), int(dogs or 1), int(price_cents or 0), notes or "",
            stripe_invoice_id or "", invoice_url or "", status or "scheduled", service_code,
            stripe_price_id or "",
        ),
    )
    booking_id = cur.lastrowid
    
    # Insert line items if provided
    if pending_items:
        insert_booking_items(conn, booking_id, pending_items)
    
    conn.commit()
    return booking_id

def insert_booking_items(conn, booking_id: int, items: list[dict]):
    """
    items: [{stripe_price_id, service_name, qty, unit_amount_cents, notes, sort_order}]
    """
    if not items:
        return
    cur = conn.cursor()
    cur.executemany(
        """INSERT INTO booking_items
           (booking_id, stripe_price_id, service_name, qty, unit_amount_cents, notes, sort_order)
           VALUES (?,?,?,?,?,?,?)""",
        [(booking_id,
          it["stripe_price_id"],
          it["service_name"],
          int(it.get("qty", 1)),
          int(it.get("unit_amount_cents", 0)),
          it.get("notes") or "",
          int(it.get("sort_order", 0)))
         for it in items]
    )
    conn.commit()

def items_for_booking(conn, booking_id: int) -> list[dict]:
    cur = conn.cursor()
    cur.execute("""
        SELECT id, stripe_price_id, service_name, qty, unit_amount_cents, notes, sort_order
        FROM booking_items
        WHERE booking_id=? ORDER BY sort_order, id
    """, (booking_id,))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

def booking_items_total_cents(conn, booking_id: int) -> int:
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(qty * unit_amount_cents),0)
        FROM booking_items WHERE booking_id=?
    """, (booking_id,))
    return int(cur.fetchone()[0] or 0)

def add_or_upsert_booking(conn, client_id, service_code, start_dt, end_dt, 
                          location, dogs, price_cents, notes, status="scheduled",
                          created_from_sub_id=None, source="manual", service_label=None):
    """
    Add or update a booking with support for subscription tracking.
    
    Args:
        conn: Database connection
        client_id: Client ID
        service_code: Service code (canonical)
        start_dt: Start datetime (ISO string)
        end_dt: End datetime (ISO string)
        location: Service location
        dogs: Number of dogs
        price_cents: Price in cents
        notes: Booking notes
        status: Booking status
        created_from_sub_id: Stripe subscription ID if from subscription
        source: Source of booking ('manual', 'subscription', etc.)
        service_label: Human-readable service label (derived from service_code if None)
    """
    from service_map import get_service_display_name
    
    if service_label is None:
        service_label = get_service_display_name(service_code, service_code)
    
    cur = conn.cursor()
    
    # Use the existing booking structure but add subscription fields
    cur.execute("""
        INSERT INTO bookings 
        (client_id, service_type, service, service_name, start_dt, end_dt, start, end, 
         location, dogs_count, dogs, price_cents, status, notes, created_from_sub_id, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        client_id, service_code, service_label, service_code, 
        start_dt, end_dt, start_dt, end_dt,
        location or "", int(dogs or 1), int(dogs or 1), int(price_cents or 0), 
        status, notes or "", created_from_sub_id, source
    ))
    
    booking_id = cur.lastrowid
    conn.commit()
    return booking_id

def set_booking_invoice(conn, booking_id, invoice_id):
    cur = conn.cursor()
    cur.execute("UPDATE bookings SET stripe_invoice_id=?, status='invoiced' WHERE id=?",
                (invoice_id, booking_id))
    conn.commit()

def update_booking_invoice(conn, booking_id: int, invoice_id: str, invoice_url: str | None):
    cur = conn.cursor()
    cur.execute("UPDATE bookings SET stripe_invoice_id=?, invoice_url=? WHERE id=?",
                (invoice_id, invoice_url or "", booking_id))
    conn.commit()
