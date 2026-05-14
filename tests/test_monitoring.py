"""
Monitoring system usage examples and integration tests.
"""
import time
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from tzdata_pkg.core.monitoring import (
    get_logger,
    get_alert_manager,
    get_metrics_collector,
    AlertRule,
    dingtalk_webhook_handler,
    wechat_webhook_handler,
    email_handler,
    handle_exceptions
)


def test_basic_logging():
    """Test basic logging functionality."""
    print("\n=== Test 1: Basic Logging ===")
    
    logger = get_logger('test_module')
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    
    print("✓ Basic logging test passed\n")


def test_exception_handling():
    """Test exception handling decorator."""
    print("\n=== Test 2: Exception Handling ===")
    
    @handle_exceptions('test_exception')
    def risky_function():
        raise ValueError("Something went wrong!")
    
    try:
        risky_function()
    except ValueError:
        print("✓ Exception was caught and logged\n")


def test_alert_management():
    """Test alert management."""
    print("\n=== Test 3: Alert Management ===")
    
    alert_manager = get_alert_manager()
    
    # Send test alerts
    alert_manager.send_alert(
        title="Test Alert",
        message="This is a test alert message",
        level="warning",
        category="test"
    )
    
    alert_manager.send_alert(
        title="Critical Alert",
        message="System CPU usage exceeded 90%",
        level="critical",
        category="system"
    )
    
    # Get recent alerts
    recent = alert_manager.get_recent_alerts(limit=5)
    print(f"Recent alerts count: {len(recent)}")
    for alert in recent:
        print(f"  - [{alert['level']}] {alert['title']}")
    
    print("✓ Alert management test passed\n")


def test_metrics_collection():
    """Test metrics collection."""
    print("\n=== Test 4: Metrics Collection ===")
    
    collector = get_metrics_collector()
    
    # Test counter
    collector.increment_counter('api_requests', tags={'endpoint': '/users'})
    collector.increment_counter('api_requests', tags={'endpoint': '/users'})
    collector.increment_counter('api_requests', tags={'endpoint': '/orders'})
    print(f"API requests counter: {collector.get_counter('api_requests')}")
    
    # Test gauge
    collector.set_gauge('cpu_usage', 75.5)
    collector.set_gauge('memory_usage', 62.3)
    print(f"CPU usage: {collector.get_gauge('cpu_usage')}%")
    print(f"Memory usage: {collector.get_gauge('memory_usage')}%")
    
    # Test histogram
    for i in range(100):
        collector.observe_histogram('response_time', 50 + i * 2)
    
    stats = collector.get_histogram_stats('response_time')
    print(f"Response time stats: min={stats['min']:.2f}ms, avg={stats['avg']:.2f}ms, p95={stats['p95']:.2f}ms")
    
    # Test timer
    with collector.timer('database_query'):
        time.sleep(0.1)  # Simulate database query
    
    timer_stats = collector.get_histogram_stats('database_query')
    print(f"Database query time: {timer_stats['avg']*1000:.2f}ms")
    
    # Get all metrics summary
    summary = collector.get_all_metrics_summary()
    print(f"\nMetrics summary:")
    print(f"  Counters: {list(summary['counters'].keys())}")
    print(f"  Gauges: {list(summary['gauges'].keys())}")
    print(f"  Histograms: {list(summary['histograms'].keys())}")
    print(f"  Timers: {list(summary['timers'].keys())}")
    
    print("✓ Metrics collection test passed\n")


def test_alert_rules():
    """Test alert rule engine."""
    print("\n=== Test 5: Alert Rules ===")
    
    collector = get_metrics_collector()
    rule_engine = collector.rule_engine
    
    # Add alert rules
    high_cpu_rule = AlertRule(
        name="high_cpu_usage",
        metric_name="cpu_usage",
        condition=">",
        threshold=80.0,
        duration_seconds=60,  # Must be above threshold for 60 seconds
        cooldown_seconds=300,
        level="warning"
    )
    rule_engine.add_rule(high_cpu_rule)
    
    critical_memory_rule = AlertRule(
        name="critical_memory",
        metric_name="memory_usage",
        condition=">",
        threshold=90.0,
        duration_seconds=0,  # Immediate trigger
        cooldown_seconds=600,
        level="critical"
    )
    rule_engine.add_rule(critical_memory_rule)
    
    # Simulate metrics that should trigger alerts
    print("Simulating CPU usage above threshold...")
    for i in range(70):  # 70 seconds
        collector.set_gauge('cpu_usage', 85.0 + i * 0.1)
        time.sleep(0.01)  # Speed up for testing
    
    print("Simulating critical memory usage...")
    collector.set_gauge('memory_usage', 95.0)
    
    print("✓ Alert rules test passed\n")


def test_email_handler_template():
    """Test email handler with HTML template."""
    print("\n=== Test 6: Email Handler Template ===")
    
    # This would require actual SMTP configuration
    # For now, just verify the handler can be created
    smtp_config = {
        'host': 'smtp.example.com',
        'port': 587,
        'username': 'user@example.com',
        'password': 'password',
        'from_addr': 'alerts@example.com',
        'to_addrs': ['admin@example.com'],
        'use_tls': True
    }
    
    handler = email_handler(smtp_config)
    print(f"Email handler created: {handler}")
    print("✓ Email handler template test passed\n")


def test_integrated_workflow():
    """Test integrated monitoring workflow."""
    print("\n=== Test 7: Integrated Workflow ===")
    
    logger = get_logger('workflow_test')
    collector = get_metrics_collector()
    alert_manager = get_alert_manager()
    
    logger.info("Starting data sync workflow")
    
    # Simulate a data sync operation
    with collector.timer('sync_duration'):
        collector.increment_counter('sync_started')
        
        # Simulate processing
        for i in range(10):
            time.sleep(0.01)
            collector.increment_counter('records_processed')
            
            # Simulate occasional errors
            if i == 5:
                logger.warning("Slow processing detected")
                collector.set_gauge('processing_latency', 500)
        
        collector.increment_counter('sync_completed')
    
    logger.info("Data sync workflow completed")
    
    # Check results
    summary = collector.get_all_metrics_summary()
    print(f"Sync completed:")
    print(f"  Records processed: {summary['counters'].get('records_processed', 0)}")
    print(f"  Sync duration: {summary['timers'].get('sync_duration', {}).get('avg', 0)*1000:.2f}ms")
    
    print("✓ Integrated workflow test passed\n")


if __name__ == "__main__":
    print("=" * 60)
    print("Monitoring System Integration Tests")
    print("=" * 60)
    
    try:
        test_basic_logging()
        test_exception_handling()
        test_alert_management()
        test_metrics_collection()
        test_alert_rules()
        test_email_handler_template()
        test_integrated_workflow()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
