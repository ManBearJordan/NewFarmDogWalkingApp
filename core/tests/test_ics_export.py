from django.test import TestCase
from django.utils import timezone
from zoneinfo import ZoneInfo
from core.ics_export import bookings_to_ics
from core.models import Client, Booking

TZ = ZoneInfo("Australia/Brisbane")

class IcsExportTestCase(TestCase):
    def test_ics_basic_and_escaping(self):
        c = Client.objects.create(name="Alice, Inc; Dogs")
        start = timezone.datetime(2025, 9, 23, 10, 0, tzinfo=TZ)
        end   = timezone.datetime(2025, 9, 23, 11, 0, tzinfo=TZ)
        b = Booking.objects.create(
            client=c,
            service_label="Walk; 60, mins",
            location="New Farm Park, Brisbane",
            notes="Bring water\nUse lead",
            start_dt=start,
            end_dt=end,
            status="confirmed",
        )
        ics = bookings_to_ics([b])
        # SUMMARY and DESCRIPTION should be escaped
        self.assertIn("SUMMARY:Walk\\; 60\\, mins", ics)
        self.assertIn("DESCRIPTION:Bring water\\nUse lead\\nClient: Alice\\, Inc\\; Dogs", ics)
        self.assertIn("DTSTART;TZID=Australia/Brisbane:20250923T100000", ics)
        self.assertIn("DTEND;TZID=Australia/Brisbane:20250923T110000", ics)
        self.assertIn("UID:", ics)
        self.assertIn("@newfarmdogwalking", ics)
        self.assertIn("PRODID:-//NewFarmDogWalking//Bookings//EN", ics)

    def test_ics_with_alarm(self):
        c = Client.objects.create(name="Bob")
        start = timezone.datetime(2025, 9, 24, 8, 0, tzinfo=TZ)
        end   = timezone.datetime(2025, 9, 24, 9, 0, tzinfo=TZ)
        b = Booking.objects.create(
            client=c,
            service_code="walk",
            start_dt=start,
            end_dt=end,
            status="confirmed",
        )
        ics = bookings_to_ics([b], alarm=True)
        self.assertIn("BEGIN:VALARM", ics)
        self.assertIn("TRIGGER:-PT5M", ics)
        self.assertIn("END:VALARM", ics)