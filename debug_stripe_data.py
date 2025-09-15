from stripe_integration import list_all_customers
from db import get_conn

print("=== Checking Stripe Customer Data ===")
try:
    customers = list_all_customers(limit=3)  # Get first 3 customers
    print(f"Retrieved {len(customers)} customers from Stripe")
    
    for i, customer in enumerate(customers, 1):
        print(f"\nCustomer {i}:")
        print(f"  Name: {customer.get('name', 'No name')}")
        print(f"  Email: {customer.get('email', 'No email')}")
        print(f"  Phone: {customer.get('phone', 'No phone')}")
        print(f"  Address: {customer.get('address', 'No address')}")
        print(f"  Stripe ID: {customer.get('id', 'No ID')}")
        
except Exception as e:
    print(f"Error retrieving Stripe data: {e}")

print("\n=== Checking Local Database ===")
conn = get_conn()
rows = conn.execute('SELECT name, email, phone, address, stripe_customer_id FROM clients LIMIT 3').fetchall()
for i, r in enumerate(rows, 1):
    print(f"\nLocal Customer {i}:")
    print(f"  Name: {r['name']}")
    print(f"  Email: {r['email']}")
    print(f"  Phone: {r['phone'] or 'No phone'}")
    print(f"  Address: {r['address'] or 'No address'}")
    print(f"  Stripe ID: {r['stripe_customer_id'] or 'No Stripe ID'}")
