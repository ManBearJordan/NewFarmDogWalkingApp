from db import get_conn

conn = get_conn()

# Check total customers
total = conn.execute('SELECT COUNT(*) as count FROM clients').fetchone()
print(f'Total customers: {total["count"]}')

# Check customers with phone numbers
phone_rows = conn.execute('SELECT COUNT(*) as count FROM clients WHERE phone IS NOT NULL AND phone != ""').fetchone()
print(f'Customers with phone numbers: {phone_rows["count"]}')

# Check customers with addresses
address_rows = conn.execute('SELECT COUNT(*) as count FROM clients WHERE address IS NOT NULL AND address != ""').fetchone()
print(f'Customers with addresses: {address_rows["count"]}')

# Show sample customers with phone/address data
print('\nSample customers with phone/address data:')
rows = conn.execute('SELECT name, email, phone, address FROM clients WHERE (phone IS NOT NULL AND phone != "") OR (address IS NOT NULL AND address != "") LIMIT 5').fetchall()
for r in rows:
    phone = r["phone"] or "No phone"
    address = r["address"] or "No address"
    print(f'- {r["name"]} ({r["email"]}) - Phone: {phone} - Address: {address}')
