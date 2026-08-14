"""
Tektos-Ultima-v1 — Runtime layer.

Provides:
    - HookRegistry: Event-driven hook system with priority ordering
    - HookManager: High-level hook lifecycle management
    - BuiltinHooks: Standard audit, thermal, and validation hooks
"""

from .hooks import (
    BuiltinHooks,
    HookContext,
    HookFn,
    HookManager,
    HookPriority,
    HookRegistry,
    HookResult,
    HookResultCode,
)

__all__ = [
    "BuiltinHooks",
    "HookContext",
    "HookFn",
    "HookManager",
    "HookPriority",
    "HookRegistry",
    "HookResult",
    "HookResultCode",
]
