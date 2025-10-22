import pytest
import logging
from django.test import RequestFactory
from core.logging_filters import RequestIDLogFilter
from core.middleware.request_id import RequestIDMiddleware


@pytest.mark.django_db
class TestRequestIDLogFilter:
    """Test the RequestIDLogFilter"""

    def test_adds_request_id_to_log_record(self):
        """Test that filter adds request_id to log records"""
        log_filter = RequestIDLogFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        result = log_filter.filter(record)
        
        assert result is True
        assert hasattr(record, "request_id")
        # Should be "-" when no request is active
        assert record.request_id == "-"

    def test_uses_current_request_id(self):
        """Test that filter uses current request ID from thread local"""
        from core.middleware.request_id import _local
        
        # Simulate active request
        _local.rid = "test-request-id-123"
        
        log_filter = RequestIDLogFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        result = log_filter.filter(record)
        
        assert result is True
        assert record.request_id == "test-request-id-123"
        
        # Clean up
        if hasattr(_local, "rid"):
            delattr(_local, "rid")

    def test_handles_missing_request_id_gracefully(self):
        """Test that filter handles missing request ID without errors"""
        log_filter = RequestIDLogFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Should not raise any exception
        result = log_filter.filter(record)
        
        assert result is True
        assert record.request_id == "-"
