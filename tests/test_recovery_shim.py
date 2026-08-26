"""Tests for src/tektos/recovery.py (thin shim that re-exports from auto_recovery).

Covers the import statements in the shim file itself.
"""

# Import from the shim to exercise the import statements
from tektos.recovery import (
    AutoRecovery,
    AutoRecoveryManager,
    GatewayManager,
    RecoveryConfig,
    RecoveryEvent,
    RecoveryReport,
    RecoveryResult,
    ServiceHealth,
    ServiceStatus,
    get_auto_recovery,
    reset_auto_recovery,
)


class TestRecoveryShim:
    """Verify the shim re-exports all expected symbols."""

    def test_auto_recovery_class(self):
        assert AutoRecovery is not None

    def test_auto_recovery_manager_class(self):
        assert AutoRecoveryManager is not None

    def test_gateway_manager_class(self):
        assert GatewayManager is not None

    def test_recovery_config_class(self):
        assert RecoveryConfig is not None

    def test_recovery_event_class(self):
        assert RecoveryEvent is not None

    def test_recovery_report_class(self):
        assert RecoveryReport is not None

    def test_recovery_result_class(self):
        assert RecoveryResult is not None

    def test_service_health_class(self):
        assert ServiceHealth is not None

    def test_service_status_class(self):
        assert ServiceStatus is not None

    def test_get_auto_recovery_function(self):
        assert callable(get_auto_recovery)

    def test_reset_auto_recovery_function(self):
        assert callable(reset_auto_recovery)

    def test_all_exports(self):
        import tektos.recovery as shim
        expected = {
            "AutoRecovery",
            "AutoRecoveryManager",
            "GatewayManager",
            "RecoveryConfig",
            "RecoveryEvent",
            "RecoveryReport",
            "RecoveryResult",
            "ServiceHealth",
            "ServiceStatus",
            "get_auto_recovery",
            "reset_auto_recovery",
            "get_events",
            "_get_all_session_ids",
        }
        assert set(shim.__all__) == expected
