import pytest
import sys
from core.apps import CoreConfig

def test_ready_noop_when_env_flag_off(monkeypatch):
    # Ensure env flag is off
    monkeypatch.setenv("STARTUP_SYNC", "0")
    # Mock settings.STARTUP_SYNC to be False
    from django.conf import settings
    monkeypatch.setattr(settings, "STARTUP_SYNC", False)
    
    # Track if Timer.start() would be called
    called = {"n": 0}
    class DummyTimer:
        def __init__(self, secs, fn): self.fn = fn
        def start(self): called["n"] += 1
    monkeypatch.setenv("RUN_MAIN", "true")
    monkeypatch.setattr("core.apps.threading.Timer", DummyTimer)
    cfg = CoreConfig("core", __import__('core'))
    cfg.ready()
    assert called["n"] == 0  # not scheduled when flag is off


def test_ready_skips_when_running_migrate(monkeypatch):
    """Test that ready() skips scheduler when 'migrate' command is in sys.argv"""
    # Enable STARTUP_SYNC so it would normally run
    monkeypatch.setenv("STARTUP_SYNC", "1")
    from django.conf import settings
    monkeypatch.setattr(settings, "STARTUP_SYNC", True)
    monkeypatch.setattr(settings, "DISABLE_SCHEDULER", False)
    
    # Mock sys.argv to contain 'migrate'
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "migrate"]
    
    # Track if Timer.start() would be called
    called = {"n": 0}
    class DummyTimer:
        def __init__(self, secs, fn): self.fn = fn
        def start(self): called["n"] += 1
    
    monkeypatch.setenv("RUN_MAIN", "true")
    monkeypatch.setattr("core.apps.threading.Timer", DummyTimer)
    
    try:
        cfg = CoreConfig("core", __import__('core'))
        cfg.ready()
        assert called["n"] == 0  # should not start when migrate is in argv
    finally:
        sys.argv = original_argv


def test_ready_skips_when_running_test(monkeypatch):
    """Test that ready() skips scheduler when 'test' command is in sys.argv"""
    # Enable STARTUP_SYNC so it would normally run
    monkeypatch.setenv("STARTUP_SYNC", "1")
    from django.conf import settings
    monkeypatch.setattr(settings, "STARTUP_SYNC", True)
    monkeypatch.setattr(settings, "DISABLE_SCHEDULER", False)
    
    # Mock sys.argv to contain 'test'
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "test"]
    
    # Track if Timer.start() would be called
    called = {"n": 0}
    class DummyTimer:
        def __init__(self, secs, fn): self.fn = fn
        def start(self): called["n"] += 1
    
    monkeypatch.setenv("RUN_MAIN", "true")
    monkeypatch.setattr("core.apps.threading.Timer", DummyTimer)
    
    try:
        cfg = CoreConfig("core", __import__('core'))
        cfg.ready()
        assert called["n"] == 0  # should not start when test is in argv
    finally:
        sys.argv = original_argv


def test_ready_skips_when_running_collectstatic(monkeypatch):
    """Test that ready() skips scheduler when 'collectstatic' command is in sys.argv"""
    # Enable STARTUP_SYNC so it would normally run
    monkeypatch.setenv("STARTUP_SYNC", "1")
    from django.conf import settings
    monkeypatch.setattr(settings, "STARTUP_SYNC", True)
    monkeypatch.setattr(settings, "DISABLE_SCHEDULER", False)
    
    # Mock sys.argv to contain 'collectstatic'
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "collectstatic"]
    
    # Track if Timer.start() would be called
    called = {"n": 0}
    class DummyTimer:
        def __init__(self, secs, fn): self.fn = fn
        def start(self): called["n"] += 1
    
    monkeypatch.setenv("RUN_MAIN", "true")
    monkeypatch.setattr("core.apps.threading.Timer", DummyTimer)
    
    try:
        cfg = CoreConfig("core", __import__('core'))
        cfg.ready()
        assert called["n"] == 0  # should not start when collectstatic is in argv
    finally:
        sys.argv = original_argv


def test_ready_skips_when_disable_scheduler_set(monkeypatch):
    """Test that ready() skips scheduler when DISABLE_SCHEDULER is True"""
    # Enable STARTUP_SYNC so it would normally run
    monkeypatch.setenv("STARTUP_SYNC", "1")
    from django.conf import settings
    monkeypatch.setattr(settings, "STARTUP_SYNC", True)
    monkeypatch.setattr(settings, "DISABLE_SCHEDULER", True)
    
    # Mock sys.argv to NOT contain management commands
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "runserver"]
    
    # Track if Timer.start() would be called
    called = {"n": 0}
    class DummyTimer:
        def __init__(self, secs, fn): self.fn = fn
        def start(self): called["n"] += 1
    
    monkeypatch.setenv("RUN_MAIN", "true")
    monkeypatch.setattr("core.apps.threading.Timer", DummyTimer)
    
    try:
        cfg = CoreConfig("core", __import__('core'))
        cfg.ready()
        assert called["n"] == 0  # should not start when DISABLE_SCHEDULER is True
    finally:
        sys.argv = original_argv


def test_ready_runs_when_no_guard_triggered(monkeypatch):
    """Test that ready() runs scheduler when no guards are triggered"""
    # Enable STARTUP_SYNC
    monkeypatch.setenv("STARTUP_SYNC", "1")
    from django.conf import settings
    monkeypatch.setattr(settings, "STARTUP_SYNC", True)
    monkeypatch.setattr(settings, "DISABLE_SCHEDULER", False)
    
    # Mock sys.argv to NOT contain management commands (normal server start)
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "runserver"]
    
    # Track if Timer.start() would be called
    called = {"n": 0}
    class DummyTimer:
        def __init__(self, secs, fn): self.fn = fn
        def start(self): called["n"] += 1
    
    monkeypatch.setenv("RUN_MAIN", "true")
    monkeypatch.setattr("core.apps.threading.Timer", DummyTimer)
    
    try:
        cfg = CoreConfig("core", __import__('core'))
        cfg.ready()
        assert called["n"] == 1  # should start when no guards are triggered
    finally:
        sys.argv = original_argv


def test_ready_runs_when_command_name_in_argument(monkeypatch):
    """Test that ready() runs scheduler when command name appears as argument, not command itself"""
    # Enable STARTUP_SYNC
    monkeypatch.setenv("STARTUP_SYNC", "1")
    from django.conf import settings
    monkeypatch.setattr(settings, "STARTUP_SYNC", True)
    monkeypatch.setattr(settings, "DISABLE_SCHEDULER", False)
    
    # Mock sys.argv where 'test' appears as an argument, not the command
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "runserver", "--settings=test"]
    
    # Track if Timer.start() would be called
    called = {"n": 0}
    class DummyTimer:
        def __init__(self, secs, fn): self.fn = fn
        def start(self): called["n"] += 1
    
    monkeypatch.setenv("RUN_MAIN", "true")
    monkeypatch.setattr("core.apps.threading.Timer", DummyTimer)
    
    try:
        cfg = CoreConfig("core", __import__('core'))
        cfg.ready()
        assert called["n"] == 1  # should start - 'test' is not at argv[1]
    finally:
        sys.argv = original_argv