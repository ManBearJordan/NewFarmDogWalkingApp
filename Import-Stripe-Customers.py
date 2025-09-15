# Import-Stripe-Customers.py
from db import get_conn
from stripe_integration import list_all_customers, stripe_mode

conn = get_conn()
cur = conn.cursor()

print("Stripe mode:", stripe_mode())

imported = updated = 0
customers = list_all_customers()
print("Stripe returned customers:", len(customers))

for cu in customers:
    cid   = cu.get("id")
    email = (cu.get("email") or "").strip()
    name  = (cu.get("name") or "").strip() or (email or cid)

    # match by email if present
    row = None
    if email:
        row = cur.execute(
            "SELECT id FROM clients WHERE lower(email)=lower(?)",
            (email,)
        ).fetchone()

    if row:
        cur.execute("UPDATE clients SET stripe_customer_id=? WHERE id=?", (cid, row["id"]))
        updated += 1
    else:
        cur.execute(
            "INSERT INTO clients(name,email,phone,address,notes,stripe_customer_id) VALUES(?,?,?,?,?,?)",
            (name, email, "", "", "", cid)
        )
        imported += 1

conn.commit()
print(f"Imported {imported}, updated {updated}")
