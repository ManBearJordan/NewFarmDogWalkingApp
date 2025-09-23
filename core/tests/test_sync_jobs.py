import os
import pytest
from django.core.management import call_command
from core.apps import CoreConfig

@pytest.mark.django_db
def test_management_command_invokes_sync(monkeypatch, capsys):
    called = {"n": 0}
    from core import subscription_sync
    monkeypatch.setattr(subscription_sync, "sync_subscriptions_to_bookings_and_calendar", lambda: called.__setitem__("n", called["n"] + 1) or {"ok": True})
    call_command("sync_subscriptions")
    assert called["n"] == 1

def test_ready_runs_startup_sync_once(monkeypatch):
    # Force STARTUP_SYNC on
    monkeypatch.setenv("STARTUP_SYNC", "1")
    # Pretend we're under the reloader's main process
    monkeypatch.setenv("RUN_MAIN", "true")

    scheduled = {"n": 0}
    # Stub Timer to call immediately instead of real threading
    class DummyTimer:
        def __init__(self, secs, fn): self.fn = fn
        def start(self): scheduled["n"] += 1; self.fn()

    monkeypatch.setattr("core.apps.threading.Timer", DummyTimer)
    
    # Mock settings.STARTUP_SYNC to be True
    from django.conf import settings
    monkeypatch.setattr(settings, "STARTUP_SYNC", True)
    
    # Stub sync function
    from core import subscription_sync
    called = {"n": 0}
    monkeypatch.setattr(subscription_sync, "sync_subscriptions_to_bookings_and_calendar", lambda: called.__setitem__("n", called["n"] + 1) or {"ok": True})

    cfg = CoreConfig("core", __import__('core'))
    # First ready() schedules once
    cfg.ready()
    # Second ready() (same process) should not schedule again
    cfg.ready()

    assert scheduled["n"] == 1
    assert called["n"] == 1