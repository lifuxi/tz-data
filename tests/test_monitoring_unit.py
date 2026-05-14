"""
Unit tests for monitoring system components.
"""
import pytest
import time
import logging
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tzdata_pkg.core.monitoring import (
    UnifiedLogger,
    AlertManager,
    AlertRule,
    AlertRuleEngine,
    MetricsCollector,
    MetricPoint,
    get_logger,
    get_alert_manager,
    get_metrics_collector,
    handle_exceptions
)


class TestUnifiedLogger:
    """Tests for UnifiedLogger."""
    
    def test_get_logger_creates_new(self):
        """Test getting a new logger."""
        logger = get_logger('test_module')
        
        assert logger is not None
        assert isinstance(logger, logging.Logger)
        assert logger.name == 'test_module'
    
    def test_get_logger_returns_cached(self):
        """Test that same logger name returns cached instance."""
        logger1 = get_logger('cached_test')
        logger2 = get_logger('cached_test')
        
        assert logger1 is logger2
    
    def test_logger_has_handlers(self):
        """Test that logger has console and file handlers."""
        logger = get_logger('handler_test')
        
        # Should have at least console handler
        assert len(logger.handlers) > 0
    
    def test_log_levels(self, caplog):
        """Test different log levels."""
        logger = get_logger('level_test')
        
        with caplog.at_level(logging.DEBUG):
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")
        
        assert "Debug message" in caplog.text
        assert "Info message" in caplog.text
        assert "Warning message" in caplog.text
        assert "Error message" in caplog.text


class TestAlertManager:
    """Tests for AlertManager."""
    
    def test_create_alert_manager(self):
        """Test creating alert manager."""
        manager = AlertManager()
        
        assert manager is not None
        assert len(manager.alert_handlers) == 0
        assert len(manager.alert_history) == 0
    
    def test_send_alert(self):
        """Test sending an alert."""
        manager = AlertManager()
        
        manager.send_alert(
            title="Test Alert",
            message="This is a test",
            level="warning",
            category="test"
        )
        
        assert len(manager.alert_history) == 1
        alert = manager.alert_history[0]
        assert alert['title'] == "Test Alert"
        assert alert['message'] == "This is a test"
        assert alert['level'] == "warning"
    
    def test_send_multiple_alerts(self):
        """Test sending multiple alerts."""
        manager = AlertManager()
        
        for i in range(5):
            manager.send_alert(
                title=f"Alert {i}",
                message=f"Message {i}",
                level="info"
            )
        
        assert len(manager.alert_history) == 5
    
    def test_alert_history_limit(self):
        """Test that alert history is limited to 1000."""
        manager = AlertManager()
        
        # Send 1001 alerts
        for i in range(1001):
            manager.send_alert(
                title=f"Alert {i}",
                message=f"Message {i}",
                level="info"
            )
        
        # Should only keep last 1000
        assert len(manager.alert_history) == 1000
        assert manager.alert_history[0]['title'] == "Alert 1"
    
    def test_get_recent_alerts(self):
        """Test getting recent alerts."""
        manager = AlertManager()
        
        for i in range(10):
            manager.send_alert(
                title=f"Alert {i}",
                message=f"Message {i}",
                level="info"
            )
        
        recent = manager.get_recent_alerts(limit=5)
        assert len(recent) == 5
        assert recent[-1]['title'] == "Alert 9"
    
    def test_register_handler(self):
        """Test registering alert handler."""
        manager = AlertManager()
        handler_called = []
        
        def test_handler(alert):
            handler_called.append(alert)
        
        manager.register_handler(test_handler)
        manager.send_alert(
            title="Test",
            message="Test message",
            level="info"
        )
        
        assert len(handler_called) == 1
        assert handler_called[0]['title'] == "Test"


class TestAlertRule:
    """Tests for AlertRule dataclass."""
    
    def test_create_rule(self):
        """Test creating an alert rule."""
        rule = AlertRule(
            name="high_cpu",
            metric_name="cpu_usage",
            condition=">",
            threshold=80.0,
            duration_seconds=300,
            cooldown_seconds=600,
            level="warning"
        )
        
        assert rule.name == "high_cpu"
        assert rule.metric_name == "cpu_usage"
        assert rule.condition == ">"
        assert rule.threshold == 80.0
        assert rule.duration_seconds == 300
        assert rule.cooldown_seconds == 600
        assert rule.level == "warning"
        assert rule.enabled is True
    
    def test_rule_defaults(self):
        """Test alert rule default values."""
        rule = AlertRule(
            name="test_rule",
            metric_name="test_metric",
            condition=">",
            threshold=100.0
        )
        
        assert rule.duration_seconds == 0
        assert rule.cooldown_seconds == 300
        assert rule.level == "warning"
        assert rule.enabled is True
        assert rule.last_triggered is None


class TestAlertRuleEngine:
    """Tests for AlertRuleEngine."""
    
    def test_create_engine(self):
        """Test creating alert rule engine."""
        engine = AlertRuleEngine()
        
        assert engine is not None
        assert len(engine.rules) == 0
    
    def test_add_rule(self):
        """Test adding a rule."""
        engine = AlertRuleEngine()
        rule = AlertRule(
            name="test_rule",
            metric_name="test_metric",
            condition=">",
            threshold=100.0
        )
        
        engine.add_rule(rule)
        
        assert len(engine.rules) == 1
        assert "test_rule" in engine.rules
    
    def test_remove_rule(self):
        """Test removing a rule."""
        engine = AlertRuleEngine()
        rule = AlertRule(
            name="test_rule",
            metric_name="test_metric",
            condition=">",
            threshold=100.0
        )
        
        engine.add_rule(rule)
        engine.remove_rule("test_rule")
        
        assert len(engine.rules) == 0
    
    def test_record_metric(self):
        """Test recording a metric value."""
        engine = AlertRuleEngine()
        
        engine.record_metric("cpu_usage", 75.5)
        
        assert "cpu_usage" in engine.metric_values
        assert len(engine.metric_values["cpu_usage"]) == 1
    
    def test_check_condition_greater_than(self):
        """Test checking '>' condition."""
        engine = AlertRuleEngine()
        
        assert engine._check_condition(85.0, ">", 80.0) is True
        assert engine._check_condition(75.0, ">", 80.0) is False
        assert engine._check_condition(80.0, ">", 80.0) is False
    
    def test_check_condition_less_than(self):
        """Test checking '<' condition."""
        engine = AlertRuleEngine()
        
        assert engine._check_condition(75.0, "<", 80.0) is True
        assert engine._check_condition(85.0, "<", 80.0) is False
    
    def test_check_condition_equals(self):
        """Test checking '==' condition."""
        engine = AlertRuleEngine()
        
        assert engine._check_condition(80.0, "==", 80.0) is True
        assert engine._check_condition(81.0, "==", 80.0) is False
    
    def test_trigger_alert_with_cooldown(self):
        """Test that cooldown prevents immediate re-triggering."""
        engine = AlertRuleEngine()
        rule = AlertRule(
            name="test_rule",
            metric_name="test_metric",
            condition=">",
            threshold=80.0,
            cooldown_seconds=60
        )
        
        engine.add_rule(rule)
        
        # First trigger
        engine.record_metric("test_metric", 85.0)
        first_trigger_time = rule.last_triggered
        
        # Immediate second record should not trigger due to cooldown
        engine.record_metric("test_metric", 90.0)
        
        # Cooldown should prevent second trigger
        assert rule.last_triggered == first_trigger_time


class TestMetricsCollector:
    """Tests for MetricsCollector."""
    
    def test_create_collector(self):
        """Test creating metrics collector."""
        collector = MetricsCollector()
        
        assert collector is not None
        assert len(collector.counters) == 0
        assert len(collector.gauges) == 0
    
    def test_increment_counter(self):
        """Test incrementing a counter."""
        collector = MetricsCollector()
        
        collector.increment_counter("api_requests")
        collector.increment_counter("api_requests")
        collector.increment_counter("api_requests", value=5)
        
        assert collector.get_counter("api_requests") == 7.0
    
    def test_set_gauge(self):
        """Test setting a gauge."""
        collector = MetricsCollector()
        
        collector.set_gauge("cpu_usage", 75.5)
        
        assert collector.get_gauge("cpu_usage") == 75.5
    
    def test_update_gauge(self):
        """Test updating a gauge."""
        collector = MetricsCollector()
        
        collector.set_gauge("cpu_usage", 75.5)
        collector.set_gauge("cpu_usage", 80.0)
        
        assert collector.get_gauge("cpu_usage") == 80.0
    
    def test_observe_histogram(self):
        """Test observing histogram values."""
        collector = MetricsCollector()
        
        for value in [50, 100, 150, 200, 250]:
            collector.observe_histogram("response_time", value)
        
        stats = collector.get_histogram_stats("response_time")
        
        assert stats['count'] == 5
        assert stats['min'] == 50
        assert stats['max'] == 250
        assert stats['avg'] == 150.0
    
    def test_histogram_percentiles(self):
        """Test histogram percentile calculations."""
        collector = MetricsCollector()
        
        # Record 100 values from 1 to 100
        for i in range(1, 101):
            collector.observe_histogram("test_metric", float(i))
        
        stats = collector.get_histogram_stats("test_metric")
        
        assert stats['p50'] == 50.0
        assert stats['p95'] == 95.0
        assert stats['p99'] == 99.0
    
    def test_record_timer(self):
        """Test recording timer duration."""
        collector = MetricsCollector()
        
        collector.record_timer("db_query", 0.5)
        collector.record_timer("db_query", 0.3)
        collector.record_timer("db_query", 0.7)
        
        stats = collector.get_histogram_stats("db_query")
        
        assert stats['count'] == 3
        assert stats['avg'] == pytest.approx(0.5, abs=0.01)
    
    def test_timer_context_manager(self):
        """Test timer as context manager."""
        collector = MetricsCollector()
        
        with collector.timer("test_operation"):
            time.sleep(0.01)  # Sleep 10ms
        
        stats = collector.get_histogram_stats("test_operation")
        assert stats['count'] == 1
        assert stats['avg'] >= 0.01
    
    def test_get_all_metrics_summary(self):
        """Test getting summary of all metrics."""
        collector = MetricsCollector()
        
        collector.increment_counter("requests", 10)
        collector.set_gauge("cpu", 75.0)
        collector.observe_histogram("latency", 100)
        collector.record_timer("query", 0.5)
        
        summary = collector.get_all_metrics_summary()
        
        assert "requests" in summary['counters']
        assert "cpu" in summary['gauges']
        assert "latency" in summary['histograms']
        assert "query" in summary['timers']
    
    def test_metric_history_limit(self):
        """Test that metric history is limited."""
        collector = MetricsCollector()
        
        # Record 1001 values
        for i in range(1001):
            collector.set_gauge("test_gauge", float(i))
        
        history = collector.get_metric_history("test_gauge")
        assert len(history) <= 1000


class TestHandleExceptions:
    """Tests for handle_exceptions decorator."""
    
    def test_decorator_catches_exception(self):
        """Test that decorator catches and logs exceptions."""
        @handle_exceptions('test_module')
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            failing_function()
    
    def test_decorator_returns_value(self):
        """Test that decorator returns function value."""
        @handle_exceptions('test_module')
        def successful_function():
            return 42
        
        result = successful_function()
        assert result == 42


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
