import pytest
from core.apps import CoreConfig

def test_ready_noop_when_env_flag_off(monkeypatch):
    # Ensure env flag is off
    monkeypatch.setenv("STARTUP_SYNC", "0")
    # Track if Timer.start() would be called
    called = {"n": 0}
    class DummyTimer:
        def __init__(self, secs, fn): self.fn = fn
        def start(self): called["n"] += 1
    monkeypatch.setenv("RUN_MAIN", "true")
    monkeypatch.setattr("core.apps.threading.Timer", DummyTimer)
    
    # Mock settings.STARTUP_SYNC to be False
    from django.conf import settings
    monkeypatch.setattr(settings, "STARTUP_SYNC", False)
    
    cfg = CoreConfig("core", __import__('core'))
    cfg.ready()
    assert called["n"] == 0  # not scheduled when flag is off