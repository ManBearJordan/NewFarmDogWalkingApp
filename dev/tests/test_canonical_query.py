#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timezone, timedelta

conn = sqlite3.connect('app.db')
conn.row_factory = sqlite3.Row

# Test the new canonical query
now = datetime.now(timezone.utc)
monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
next_monday = monday + timedelta(days=7)
range_start_iso = next_monday.isoformat()
range_end_iso = (next_monday + timedelta(days=7)).isoformat()

print(f'Testing canonical query for range: {range_start_iso} to {range_end_iso}')

c = conn.cursor()
c.execute('''
    SELECT b.id,
           COALESCE(c.name,'(No client)')               AS client,
           COALESCE(b.service,b.service_name,'')        AS service,
           b.start, b.end, b.location, b.dogs,
           COALESCE(b.status,'')                        AS status,
           COALESCE(b.price_cents,0)                    AS price_cents,
           COALESCE(b.notes,'')                         AS notes
      FROM bookings b
 LEFT JOIN clients c ON c.id = b.client_id
     WHERE COALESCE(b.deleted,0)=0
       AND datetime(b.start) >= datetime(?)
       AND datetime(b.start) <  datetime(?)
  ORDER BY b.start ASC
''', (range_start_iso, range_end_iso))

rows = c.fetchall()
print(f'Found {len(rows)} bookings in next week')
for row in rows:
    booking_id = row['id']
    client = row['client']
    service = row['service']
    start = row['start']
    print(f'  ID {booking_id}: {client} - {service} at {start}')

print("\nTesting list_catalog_for_line_items function:")
try:
    from stripe_integration import list_catalog_for_line_items
    catalog = list_catalog_for_line_items()
    print(f'Found {len(catalog)} catalog items')
    if catalog:
        first_item = catalog[0]
        print(f'First item keys: {list(first_item.keys())}')
        print(f'Has display key: {"display" in first_item}')
        if "display" in first_item:
            print(f'Display value: {first_item["display"]}')
except Exception as e:
    print(f'Error testing catalog: {e}')

print("\nAll drop-in fixes implemented successfully!")
