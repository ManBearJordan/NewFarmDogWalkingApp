import pytest
from django.utils import timezone
from zoneinfo import ZoneInfo
from core.ics_export import bookings_to_ics
from core.models import Client, Booking

TZ = ZoneInfo("Australia/Brisbane")

@pytest.mark.django_db
def test_alarm_minutes_bad_input_falls_back_to_5():
    c = Client.objects.create(name="Edge")
    b = Booking.objects.create(
        client=c, service_code="walk",
        start_dt=timezone.datetime(2025,9,24,9,0,tzinfo=TZ),
        end_dt=timezone.datetime(2025,9,24,10,0,tzinfo=TZ),
        status="confirmed"
    )
    # Pass a non-int; helper should fall back to 5 minutes
    ics = bookings_to_ics([b], alarm=True, alarm_minutes="not_an_int")  # type: ignore[arg-type]
    assert "BEGIN:VALARM" in ics
    assert "TRIGGER:-PT5M" in ics

@pytest.mark.django_db
def test_alarm_minutes_under_minimum_clamped_to_1():
    c = Client.objects.create(name="Edge2")
    b = Booking.objects.create(
        client=c, service_code="walk",
        start_dt=timezone.datetime(2025,9,25,9,0,tzinfo=TZ),
        end_dt=timezone.datetime(2025,9,25,10,0,tzinfo=TZ),
        status="confirmed"
    )
    ics = bookings_to_ics([b], alarm=True, alarm_minutes=0)
    assert "TRIGGER:-PT1M" in ics