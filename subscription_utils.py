import unicodedata
import re
from datetime import datetime

from db import get_conn

# Try to import central service_map helper if present
try:
    from service_map import get_service_code
except Exception:
    get_service_code = None


def _safe_log(msg: str):
    try:
        with open("subscription_error_log.txt", "a") as f:
            f.write(f"{datetime.utcnow().isoformat()} - {msg}\n")
    except Exception:
        # best-effort logging
        pass


def resolve_client_for_subscription(conn, subscription) -> int:
    """
    Resolve or create a local client for the given Stripe subscription object/dict.
    Returns client_id (int).
    """
    cur = conn.cursor()
    try:
        customer = subscription.get("customer") if isinstance(subscription, dict) else getattr(subscription, "customer", None)
        # customer may be an object or id; try to extract email and id
        customer_email = None
        stripe_customer_id = None
        if isinstance(customer, dict):
            customer_email = customer.get("email")
            stripe_customer_id = customer.get("id")
        else:
            # object-like
            stripe_customer_id = getattr(customer, "id", None)
            customer_email = getattr(customer, "email", None)

        # 1) Try email match
        if customer_email:
            row = cur.execute("SELECT id FROM clients WHERE LOWER(email) = LOWER(?) LIMIT 1", (customer_email,)).fetchone()
            if row:
                return row[0]

        # 2) Try stripe_customer_id in both possible columns
        if stripe_customer_id:
            row = cur.execute("SELECT id FROM clients WHERE stripe_customer_id = ? LIMIT 1", (stripe_customer_id,)).fetchone()
            if row:
                return row[0]
            row = cur.execute("SELECT id FROM clients WHERE stripeCustomerId = ? LIMIT 1", (stripe_customer_id,)).fetchone()
            if row:
                return row[0]

        # 3) Not found: create placeholder client so bookings can be generated
        name = customer_email or f"stripe_customer_{stripe_customer_id or 'unknown'}"
        try:
            cur.execute(
                "INSERT INTO clients (name, email, stripe_customer_id, notes) VALUES (?, ?, ?, ?)",
                (name, customer_email, stripe_customer_id, "Auto-created placeholder client from subscription sync")
            )
            conn.commit()
            return cur.lastrowid
        except Exception as e:
            _safe_log(f"Failed to create placeholder client for subscription {subscription.get('id', getattr(subscription, 'id', 'unknown'))}: {e}")
            return None
    except Exception as e:
        _safe_log(f"Error resolving client for subscription {subscription.get('id', getattr(subscription, 'id', 'unknown'))}: {e}")
        return None


def service_type_from_label(label: str) -> str:
    """
    Normalize a human label into a canonical service_type code. Prefer the central service_map if available.
    """
    if not label:
        return "UNKNOWN_SERVICE"

    # Try central map helper if present
    try:
        if get_service_code:
            code = get_service_code(label)
            if code:
                return code
    except Exception:
        pass

    # Fallback normalization: replace special chars first, then normalize and clean
    # Replace special characters before unicode normalization
    s = label.replace("×", "x")  # multiplication sign to x
    s = s.replace("—", "-").replace("–", "-")  # em/en dash to hyphen  
    s = s.replace("•", "")  # bullet point
    
    # Remove diacritics and convert to ASCII
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    
    # Remove parentheses content
    s = re.sub(r"\([^)]*\)", "", s)
    # Replace non-alphanumeric runs with underscore
    s = re.sub(r"[^0-9A-Za-z]+", "_", s)
    s = s.strip("_")
    if not s:
        return "UNKNOWN_SERVICE"
    return s.upper()