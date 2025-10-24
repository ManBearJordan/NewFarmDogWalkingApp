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
    monkeypatch.setattr(settings, "IS_MANAGEMENT_CMD", True)  # Mock the flag
    
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
    monkeypatch.setattr(settings, "IS_MANAGEMENT_CMD", True)  # Mock the flag
    
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
    monkeypatch.setattr(settings, "IS_MANAGEMENT_CMD", True)  # Mock the flag
    
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


def test_is_management_cmd_flag_set_for_migrate(monkeypatch):
    """Test that IS_MANAGEMENT_CMD flag is set correctly for migrate"""
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "migrate"]
    
    try:
        # Reimport settings to pick up sys.argv change
        import importlib
        from newfarm import settings
        importlib.reload(settings)
        
        assert settings.IS_MANAGEMENT_CMD is True
    finally:
        sys.argv = original_argv


def test_is_management_cmd_flag_not_set_for_runserver(monkeypatch):
    """Test that IS_MANAGEMENT_CMD flag is False for runserver"""
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "runserver"]
    
    try:
        # Reimport settings to pick up sys.argv change
        import importlib
        from newfarm import settings
        importlib.reload(settings)
        
        assert settings.IS_MANAGEMENT_CMD is False
    finally:
        sys.argv = original_argv


def test_ready_returns_early_when_is_management_cmd_set(monkeypatch):
    """Test that ready() returns early when IS_MANAGEMENT_CMD is set"""
    from django.conf import settings
    from unittest.mock import patch, MagicMock
    
    # Set IS_MANAGEMENT_CMD to True
    monkeypatch.setattr(settings, "IS_MANAGEMENT_CMD", True)
    
    # Mock the scheduler import to detect if it's called
    mock_scheduler = MagicMock()
    
    with patch.dict('sys.modules', {'core.scheduler': mock_scheduler}):
        cfg = CoreConfig("core", __import__('core'))
        cfg.ready()
        
        # Scheduler should not be imported or started
        # The function should return early
        # We can't directly test if return happened, but we can verify scheduler wasn't started
        mock_scheduler.start_scheduler_if_enabled.assert_not_called()