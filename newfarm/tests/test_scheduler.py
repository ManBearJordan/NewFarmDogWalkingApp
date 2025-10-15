import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from newfarm.apps import NewfarmConfig


def test_scheduler_starts_with_periodic_sync(monkeypatch):
    """Test that scheduler starts when PERIODIC_SYNC=1"""
    monkeypatch.setenv("PERIODIC_SYNC", "1")
    monkeypatch.setenv("SYNC_INTERVAL_MINUTES", "15")
    monkeypatch.setenv("RUN_MAIN", "true")
    
    with patch('newfarm.scheduler.BackgroundScheduler') as mock_scheduler_class:
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler
        
        from newfarm.scheduler import start_scheduler
        # Reset the global state for testing
        import newfarm.scheduler as sched_module
        sched_module._scheduler_started = False
        sched_module._scheduler = None
        
        start_scheduler()
        
        # Verify scheduler was created and started
        mock_scheduler_class.assert_called_once()
        mock_scheduler.start.assert_called_once_with(paused=True)
        mock_scheduler.resume.assert_called_once()
        # Should have added periodic job
        assert mock_scheduler.add_job.call_count >= 1


def test_scheduler_starts_with_startup_sync(monkeypatch):
    """Test that scheduler starts when STARTUP_SYNC=1"""
    monkeypatch.setenv("STARTUP_SYNC", "1")
    monkeypatch.setenv("RUN_MAIN", "true")
    
    with patch('newfarm.scheduler.BackgroundScheduler') as mock_scheduler_class:
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler
        
        from newfarm.scheduler import start_scheduler
        # Reset the global state for testing
        import newfarm.scheduler as sched_module
        sched_module._scheduler_started = False
        sched_module._scheduler = None
        
        start_scheduler()
        
        # Verify scheduler was created
        mock_scheduler_class.assert_called_once()
        mock_scheduler.add_job.assert_called()


def test_scheduler_not_started_twice(monkeypatch):
    """Test that scheduler doesn't start twice in the same process"""
    monkeypatch.setenv("PERIODIC_SYNC", "1")
    
    with patch('newfarm.scheduler.BackgroundScheduler') as mock_scheduler_class:
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler
        
        from newfarm.scheduler import start_scheduler
        # Reset the global state for testing
        import newfarm.scheduler as sched_module
        sched_module._scheduler_started = False
        sched_module._scheduler = None
        
        start_scheduler()
        start_scheduler()  # Second call
        
        # Should only be called once
        assert mock_scheduler_class.call_count == 1


def test_appconfig_ready_starts_scheduler(monkeypatch):
    """Test that NewfarmConfig.ready() starts the scheduler"""
    monkeypatch.setenv("RUN_MAIN", "true")
    monkeypatch.setenv("PERIODIC_SYNC", "1")
    
    with patch('newfarm.scheduler.start_scheduler') as mock_start:
        config = NewfarmConfig("newfarm", __import__('newfarm'))
        config.ready()
        
        mock_start.assert_called_once()


def test_appconfig_ready_skips_in_reloader(monkeypatch):
    """Test that NewfarmConfig.ready() skips when RUN_MAIN is not true"""
    monkeypatch.setenv("RUN_MAIN", "false")
    
    with patch('newfarm.scheduler.start_scheduler') as mock_start:
        config = NewfarmConfig("newfarm", __import__('newfarm'))
        config.ready()
        
        mock_start.assert_not_called()


@pytest.mark.django_db
def test_run_sync_job_calls_command(monkeypatch):
    """Test that _run_sync_job calls the full sync pipeline"""
    with patch('newfarm.scheduler.call_command') as mock_call:
        from newfarm.scheduler import _run_sync_job
        _run_sync_job()
        
        # Should call customers, subscriptions, and bookings commands
        assert mock_call.call_count == 3
        # Check that it tried to call these commands (order matters)
        calls = [str(c) for c in mock_call.call_args_list]
        assert any("sync_customers" in c for c in calls)
        assert any("sync_subscriptions" in c for c in calls)
        assert any("build_bookings" in c for c in calls)
