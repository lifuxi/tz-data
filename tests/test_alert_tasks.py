"""DingTalk alert task tests.

Tests for:
- _get_dingtalk_webhook() priority (system_config > env fallback)
- DingTalk handler registration with AlertManager
- Sync failure alert triggering
- Webhook send failure resilience
"""
import os
from unittest.mock import patch, MagicMock

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tzdata_pkg.core.monitoring import AlertManager


class TestGetDingtalkWebhook:
    """Test webhook URL resolution priority."""

    def test_system_config_takes_priority(self):
        """system_config value should override env var."""
        with patch('tzdata_pkg.config._get_system_config_value', return_value="https://oapi.dingtalk.com/webhook?code=CONFIG"):
            from tzdata_pkg.scheduler.tasks.alert_tasks import _get_dingtalk_webhook
            result = _get_dingtalk_webhook()
            assert result == "https://oapi.dingtalk.com/webhook?code=CONFIG"

    def test_fallback_to_env(self):
        """Should fallback to env var when system_config is unavailable."""
        with patch('tzdata_pkg.config._get_system_config_value', side_effect=Exception("not found")):
            old_val = os.environ.get("DINGTALK_WEBHOOK_URL")
            try:
                os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/webhook?code=ENV"
                from tzdata_pkg.scheduler.tasks.alert_tasks import _get_dingtalk_webhook
                result = _get_dingtalk_webhook()
                assert result == "https://oapi.dingtalk.com/webhook?code=ENV"
            finally:
                if old_val is None:
                    os.environ.pop("DINGTALK_WEBHOOK_URL", None)
                else:
                    os.environ["DINGTALK_WEBHOOK_URL"] = old_val

    def test_returns_empty_string_when_unconfigured(self):
        """Both system_config and env missing → empty string."""
        with patch('tzdata_pkg.config._get_system_config_value', side_effect=Exception("not found")):
            old_val = os.environ.get("DINGTALK_WEBHOOK_URL")
            try:
                os.environ.pop("DINGTALK_WEBHOOK_URL", None)
                from tzdata_pkg.scheduler.tasks.alert_tasks import _get_dingtalk_webhook
                result = _get_dingtalk_webhook()
                assert result == ""
            finally:
                if old_val is not None:
                    os.environ["DINGTALK_WEBHOOK_URL"] = old_val


class TestAlertManagerRegistration:
    """Test DingTalk handler registration."""

    def test_handler_registered_on_init(self):
        """DingTalk handler should be registered when _init_alerts() is called with valid webhook."""
        fresh_am = AlertManager()

        with patch('tzdata_pkg.scheduler.tasks.alert_tasks._get_dingtalk_webhook', return_value="https://fake.dingtalk.com/webhook"):
            with patch('tzdata_pkg.scheduler.tasks.alert_tasks._get_dingtalk_secret', return_value=""):
                with patch('tzdata_pkg.scheduler.tasks.alert_tasks.dingtalk_webhook_handler', return_value=lambda alert: None):
                    with patch('tzdata_pkg.core.monitoring._alert_manager', fresh_am):
                        from tzdata_pkg.scheduler.tasks.alert_tasks import _init_alerts, _initialized
                        # Reset global state
                        import tzdata_pkg.scheduler.tasks.alert_tasks as alert_mod
                        alert_mod._initialized = False

                        _init_alerts()

                        assert len(fresh_am.alert_handlers) == 1

    def test_no_registration_without_webhook(self):
        """No handler registered when webhook is empty."""
        fresh_am = AlertManager()

        with patch('tzdata_pkg.scheduler.tasks.alert_tasks._get_dingtalk_webhook', return_value=""):
            with patch('tzdata_pkg.core.monitoring._alert_manager', fresh_am):
                import tzdata_pkg.scheduler.tasks.alert_tasks as alert_mod
                alert_mod._initialized = False

                from tzdata_pkg.scheduler.tasks.alert_tasks import _init_alerts
                _init_alerts()

                assert len(fresh_am.alert_handlers) == 0

    def test_init_is_idempotent(self):
        """Calling _init_alerts() twice should not register duplicate handlers."""
        fresh_am = AlertManager()

        with patch('tzdata_pkg.scheduler.tasks.alert_tasks._get_dingtalk_webhook', return_value="https://fake.dingtalk.com/webhook"):
            with patch('tzdata_pkg.scheduler.tasks.alert_tasks._get_dingtalk_secret', return_value=""):
                with patch('tzdata_pkg.scheduler.tasks.alert_tasks.dingtalk_webhook_handler', return_value=lambda alert: None):
                    with patch('tzdata_pkg.core.monitoring._alert_manager', fresh_am):
                        import tzdata_pkg.scheduler.tasks.alert_tasks as alert_mod
                        alert_mod._initialized = False

                        from tzdata_pkg.scheduler.tasks.alert_tasks import _init_alerts
                        _init_alerts()
                        _init_alerts()

                        assert len(fresh_am.alert_handlers) == 1


class TestSendSyncAlert:
    """Test sync alert sending."""

    def test_sync_alert_triggered(self):
        """Sync failure should trigger alert with correct message."""
        fresh_am = AlertManager()

        with patch('tzdata_pkg.core.monitoring._alert_manager', fresh_am):
            with patch('tzdata_pkg.scheduler.tasks.alert_tasks._init_alerts'):
                from tzdata_pkg.scheduler.tasks.alert_tasks import send_sync_alert

                send_sync_alert(
                    task_name="mo-iv-sync",
                    status="error",
                    message="IV sync failed: timeout",
                    trade_date="2025-06-01",
                    details={"retry": 3},
                )

                assert len(fresh_am.alert_history) == 1
                alert = fresh_am.alert_history[0]
                assert "mo-iv-sync" in alert["title"]
                assert alert["level"] == "error"
                assert "IV sync failed: timeout" in alert["message"]

    def test_webhook_send_failure_does_not_crash(self):
        """If webhook POST fails, send_alert should not raise."""
        def failing_handler(alert):
            raise ConnectionError("webhook unreachable")

        fresh_am = AlertManager()
        fresh_am.register_handler(failing_handler)

        with patch('tzdata_pkg.core.monitoring._alert_manager', fresh_am):
            with patch('tzdata_pkg.scheduler.tasks.alert_tasks._init_alerts'):
                from tzdata_pkg.scheduler.tasks.alert_tasks import send_sync_alert

                # Should not raise
                send_sync_alert(
                    task_name="mo-minute-sync",
                    status="warning",
                    message="partial data",
                )

                # Alert still recorded in history
                assert len(fresh_am.alert_history) == 1


class TestSendBillAlert:
    """Test bill-specific alert sending."""

    def test_bill_alert_format(self):
        """Bill alert should include account name and missing days."""
        fresh_am = AlertManager()

        with patch('tzdata_pkg.core.monitoring._alert_manager', fresh_am):
            with patch('tzdata_pkg.scheduler.tasks.alert_tasks._init_alerts'):
                from tzdata_pkg.scheduler.tasks.alert_tasks import send_bill_alert

                send_bill_alert(
                    account_name="Test Account",
                    missing_days=3,
                    latest_missing="2025-05-15",
                )

                assert len(fresh_am.alert_history) == 1
                alert = fresh_am.alert_history[0]
                assert "Test Account" in alert["title"]
                assert "3" in alert["message"]
                assert "2025-05-15" in alert["message"]
                assert alert["category"] == "bill"
                assert alert["level"] == "warning"
