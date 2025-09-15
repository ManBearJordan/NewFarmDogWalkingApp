\
from icalendar import Calendar, Event
from datetime import datetime
from dateutil import tz

def export_bookings(bookings, filepath, tz_name="Australia/Brisbane"):
    cal = Calendar()
    cal.add('prodid', '-//New Farm Dog Walking//')
    cal.add('version', '2.0')
    tzinfo = tz.gettz(tz_name)
    for b in bookings:
        ev = Event()
        ev.add('summary', f"{b['service_type']} — {b['client_name']}")
        ev.add('dtstart', datetime.fromisoformat(b['start_dt']).replace(tzinfo=tzinfo))
        ev.add('dtend', datetime.fromisoformat(b['end_dt']).replace(tzinfo=tzinfo))
        ev.add('location', b.get('location') or '')
        ev.add('description', b.get('notes') or '')
        cal.add_component(ev)
    with open(filepath, 'wb') as f:
        f.write(cal.to_ical())
