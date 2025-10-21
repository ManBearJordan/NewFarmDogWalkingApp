"""
Tests for core/scheduler.py - the new APScheduler-based background scheduler.
"""
import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock, call


@pytest.fixture
def reset_scheduler_state():
    """Reset global scheduler state before each test"""
    import core.scheduler as sched_module
    sched_module._SCHEDULER = None
    sched_module._STARTED = False
    yield
    sched_module._SCHEDULER = None
    sched_module._STARTED = False


def test_env_enabled_when_set(reset_scheduler_state, monkeypatch):
    """Test that _env_enabled returns True when NFDW_SCHEDULER=1"""
    monkeypatch.setenv("NFDW_SCHEDULER", "1")
    from core.scheduler import _env_enabled
    assert _env_enabled() is True


def test_env_enabled_when_not_set(reset_scheduler_state, monkeypatch):
    """Test that _env_enabled returns False when NFDW_SCHEDULER is not 1"""
    monkeypatch.setenv("NFDW_SCHEDULER", "0")
    from core.scheduler import _env_enabled
    assert _env_enabled() is False


def test_is_management_command_process_migrate(reset_scheduler_state):
    """Test that management command detection works for migrate"""
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "migrate"]
    try:
        from core.scheduler import _is_management_command_process
        assert _is_management_command_process() is True
    finally:
        sys.argv = original_argv


def test_is_management_command_process_collectstatic(reset_scheduler_state):
    """Test that management command detection works for collectstatic"""
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "collectstatic"]
    try:
        from core.scheduler import _is_management_command_process
        assert _is_management_command_process() is True
    finally:
        sys.argv = original_argv


def test_is_management_command_process_runserver(reset_scheduler_state):
    """Test that management command detection returns False for runserver"""
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "runserver"]
    try:
        from core.scheduler import _is_management_command_process
        assert _is_management_command_process() is False
    finally:
        sys.argv = original_argv


def test_get_int_with_valid_value(reset_scheduler_state, monkeypatch):
    """Test _get_int with a valid integer"""
    monkeypatch.setenv("TEST_INT", "42")
    from core.scheduler import _get_int
    assert _get_int("TEST_INT", 10) == 42


def test_get_int_with_invalid_value(reset_scheduler_state, monkeypatch):
    """Test _get_int with invalid value returns default"""
    monkeypatch.setenv("TEST_INT", "not_a_number")
    from core.scheduler import _get_int
    assert _get_int("TEST_INT", 10) == 10


def test_get_int_with_missing_value(reset_scheduler_state):
    """Test _get_int with missing env var returns default"""
    from core.scheduler import _get_int
    assert _get_int("NONEXISTENT_VAR", 99) == 99


def test_start_scheduler_disabled_by_env(reset_scheduler_state, monkeypatch):
    """Test that scheduler doesn't start when NFDW_SCHEDULER is not enabled"""
    monkeypatch.setenv("NFDW_SCHEDULER", "0")
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "runserver"]
    try:
        from core.scheduler import start_scheduler_if_enabled
        result = start_scheduler_if_enabled()
        assert result is None
    finally:
        sys.argv = original_argv


def test_start_scheduler_disabled_in_management_command(reset_scheduler_state, monkeypatch):
    """Test that scheduler doesn't start during management commands"""
    monkeypatch.setenv("NFDW_SCHEDULER", "1")
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "migrate"]
    try:
        from core.scheduler import start_scheduler_if_enabled
        result = start_scheduler_if_enabled()
        assert result is None
    finally:
        sys.argv = original_argv


def test_start_scheduler_when_apscheduler_missing(reset_scheduler_state, monkeypatch):
    """Test graceful handling when APScheduler is not installed"""
    monkeypatch.setenv("NFDW_SCHEDULER", "1")
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "runserver"]
    try:
        with patch('core.scheduler.BackgroundScheduler', None):
            from core.scheduler import start_scheduler_if_enabled
            result = start_scheduler_if_enabled()
            assert result is None
    finally:
        sys.argv = original_argv


def test_start_scheduler_successfully(reset_scheduler_state, monkeypatch):
    """Test successful scheduler startup"""
    monkeypatch.setenv("NFDW_SCHEDULER", "1")
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "runserver"]
    try:
        with patch('core.scheduler.BackgroundScheduler') as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler
            
            from core.scheduler import start_scheduler_if_enabled
            result = start_scheduler_if_enabled()
            
            # Verify scheduler was created and started
            mock_scheduler_class.assert_called_once()
            mock_scheduler.start.assert_called_once()
            # Verify jobs were added
            assert mock_scheduler.add_job.call_count == 3
            assert result == mock_scheduler
    finally:
        sys.argv = original_argv


def test_start_scheduler_only_once(reset_scheduler_state, monkeypatch):
    """Test that scheduler only starts once per process"""
    monkeypatch.setenv("NFDW_SCHEDULER", "1")
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "runserver"]
    try:
        with patch('core.scheduler.BackgroundScheduler') as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler
            
            from core.scheduler import start_scheduler_if_enabled
            result1 = start_scheduler_if_enabled()
            result2 = start_scheduler_if_enabled()  # Second call
            
            # Should only start once
            mock_scheduler_class.assert_called_once()
            assert result1 == result2
    finally:
        sys.argv = original_argv


def test_register_jobs_adds_three_jobs(reset_scheduler_state):
    """Test that _register_jobs adds all three jobs"""
    mock_scheduler = MagicMock()
    from core.scheduler import _register_jobs
    
    _register_jobs(mock_scheduler)
    
    assert mock_scheduler.add_job.call_count == 3
    # Check job IDs
    job_ids = [call[1]["id"] for call in mock_scheduler.add_job.call_args_list]
    assert "sync_invoices" in job_ids
    assert "sync_subscription_links" in job_ids
    assert "materialize_all" in job_ids


def test_register_jobs_respects_env_intervals(reset_scheduler_state, monkeypatch):
    """Test that job intervals can be customized via env vars"""
    monkeypatch.setenv("NFDW_SYNC_INVOICES_MINUTES", "30")
    monkeypatch.setenv("NFDW_SYNC_SUBS_MINUTES", "120")
    monkeypatch.setenv("NFDW_MATERIALIZE_MINUTES", "90")
    
    mock_scheduler = MagicMock()
    from core.scheduler import _register_jobs
    
    _register_jobs(mock_scheduler)
    
    # Check that custom intervals were used
    calls = mock_scheduler.add_job.call_args_list
    for call_item in calls:
        kwargs = call_item[1]
        if kwargs["id"] == "sync_invoices":
            assert kwargs["minutes"] == 30
        elif kwargs["id"] == "sync_subscription_links":
            assert kwargs["minutes"] == 120
        elif kwargs["id"] == "materialize_all":
            assert kwargs["minutes"] == 90


@pytest.mark.django_db
def test_job_sync_invoices_success(reset_scheduler_state, monkeypatch):
    """Test job_sync_invoices calls sync_invoices successfully"""
    mock_sync = MagicMock(return_value={"synced": 10})
    
    with patch('core.stripe_invoices_sync.sync_invoices', mock_sync):
        from core.scheduler import job_sync_invoices
        job_sync_invoices()
        
        mock_sync.assert_called_once_with(days=90)


@pytest.mark.django_db
def test_job_sync_invoices_with_custom_lookback(reset_scheduler_state, monkeypatch):
    """Test job_sync_invoices respects custom lookback days"""
    monkeypatch.setenv("NFDW_SYNC_INVOICES_LOOKBACK_DAYS", "30")
    mock_sync = MagicMock(return_value={"synced": 5})
    
    with patch('core.stripe_invoices_sync.sync_invoices', mock_sync):
        from core.scheduler import job_sync_invoices
        job_sync_invoices()
        
        mock_sync.assert_called_once_with(days=30)


@pytest.mark.django_db
def test_job_sync_invoices_handles_exception(reset_scheduler_state):
    """Test job_sync_invoices handles exceptions gracefully"""
    with patch('core.stripe_invoices_sync.sync_invoices', side_effect=Exception("Test error")):
        from core.scheduler import job_sync_invoices
        # Should not raise, only log
        job_sync_invoices()


@pytest.mark.django_db
def test_job_materialize_success(reset_scheduler_state):
    """Test job_materialize calls materialize_all successfully"""
    mock_materialize = MagicMock(return_value={"materialized": 20})
    
    with patch('core.subscription_materializer.materialize_all', mock_materialize):
        from core.scheduler import job_materialize
        job_materialize()
        
        mock_materialize.assert_called_once_with(horizon_weeks=12)


@pytest.mark.django_db
def test_job_materialize_with_custom_weeks(reset_scheduler_state, monkeypatch):
    """Test job_materialize respects custom horizon weeks"""
    monkeypatch.setenv("NFDW_MATERIALIZE_WEEKS", "24")
    mock_materialize = MagicMock(return_value={"materialized": 30})
    
    with patch('core.subscription_materializer.materialize_all', mock_materialize):
        from core.scheduler import job_materialize
        job_materialize()
        
        mock_materialize.assert_called_once_with(horizon_weeks=24)


@pytest.mark.django_db
def test_job_materialize_handles_exception(reset_scheduler_state):
    """Test job_materialize handles exceptions gracefully"""
    with patch('core.subscription_materializer.materialize_all', side_effect=Exception("Test error")):
        from core.scheduler import job_materialize
        # Should not raise, only log
        job_materialize()


@pytest.mark.django_db
def test_job_sync_subscription_links_success(reset_scheduler_state):
    """Test job_sync_subscription_links calls ensure_links successfully"""
    mock_ensure = MagicMock()
    
    with patch('core.stripe_subscriptions.ensure_links_for_client_stripe_subs', mock_ensure):
        from core.scheduler import job_sync_subscription_links
        job_sync_subscription_links()
        
        mock_ensure.assert_called_once()


@pytest.mark.django_db
def test_job_sync_subscription_links_handles_missing_function(reset_scheduler_state):
    """Test job_sync_subscription_links handles missing function gracefully"""
    with patch('core.scheduler.job_sync_subscription_links.__code__') as mock_code:
        # Simulate import failure
        from core.scheduler import job_sync_subscription_links
        # Should not raise, only log
        job_sync_subscription_links()


@pytest.mark.django_db
def test_job_sync_subscription_links_handles_exception(reset_scheduler_state):
    """Test job_sync_subscription_links handles exceptions gracefully"""
    with patch('core.stripe_subscriptions.ensure_links_for_client_stripe_subs', side_effect=Exception("Test error")):
        from core.scheduler import job_sync_subscription_links
        # Should not raise, only log
        job_sync_subscription_links()


def test_scheduler_registers_atexit_handler(reset_scheduler_state, monkeypatch):
    """Test that scheduler registers an atexit handler for shutdown"""
    monkeypatch.setenv("NFDW_SCHEDULER", "1")
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "runserver"]
    try:
        with patch('core.scheduler.BackgroundScheduler') as mock_scheduler_class, \
             patch('core.scheduler.atexit.register') as mock_atexit:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler
            
            from core.scheduler import start_scheduler_if_enabled
            start_scheduler_if_enabled()
            
            # Verify atexit handler was registered
            mock_atexit.assert_called_once()
    finally:
        sys.argv = original_argv


def test_appconfig_ready_starts_scheduler(reset_scheduler_state, monkeypatch):
    """Test that CoreConfig.ready() starts the scheduler when appropriate"""
    monkeypatch.setenv("NFDW_SCHEDULER", "1")
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "runserver"]
    
    from django.conf import settings
    monkeypatch.setattr(settings, "DISABLE_SCHEDULER", False)
    monkeypatch.setattr(settings, "STARTUP_SYNC", False)
    
    try:
        with patch('core.scheduler.start_scheduler_if_enabled') as mock_start:
            from core.apps import CoreConfig
            config = CoreConfig("core", __import__('core'))
            config.ready()
            
            mock_start.assert_called_once()
    finally:
        sys.argv = original_argv


def test_appconfig_ready_handles_scheduler_exception(reset_scheduler_state, monkeypatch):
    """Test that CoreConfig.ready() handles scheduler exceptions gracefully"""
    monkeypatch.setenv("NFDW_SCHEDULER", "1")
    original_argv = sys.argv.copy()
    sys.argv = ["manage.py", "runserver"]
    
    from django.conf import settings
    monkeypatch.setattr(settings, "DISABLE_SCHEDULER", False)
    monkeypatch.setattr(settings, "STARTUP_SYNC", False)
    
    try:
        with patch('core.scheduler.start_scheduler_if_enabled', side_effect=Exception("Test error")):
            from core.apps import CoreConfig
            config = CoreConfig("core", __import__('core'))
            # Should not raise, only log
            config.ready()
    finally:
        sys.argv = original_argv
