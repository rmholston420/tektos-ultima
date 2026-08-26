"""Auto-recovery on server restart.

This module is a thin shim. All classes live in tektos.recovery.auto_recovery
to avoid circular imports caused by the recovery/ package shadowing this file.

Recover state when Tektos restarts:
- Loads last known state from LAST_KNOWN_STATE.md / Hindsight
- Recovers interrupted sessions from event store
- Restores gateway connections (Telegram/Email)
- Notifies admin of recovered state

Usage:
    from tektos.recovery import AutoRecoveryManager

    async with AutoRecoveryManager(state_manager, event_store) as recovery:
        results = await recovery.recover()
        # results: dict of what was recovered
"""

from tektos.recovery.auto_recovery import (
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

__all__ = [
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
]
