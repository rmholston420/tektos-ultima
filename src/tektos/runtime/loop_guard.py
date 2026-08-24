"""Tool-call loop guard — SHA-256 pattern detection for stuck agent loops.

Tracks recent tool calls with SHA-256 hashing + sliding window.
After 3 identical calls → warning phase (suggest alternative).
After 5 identical calls → block phase (force strategy change).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("tektos.loop_guard")


@dataclass
class ToolCallHash:
    """Hash of a tool call for loop detection."""
    tool_name: str
    arg_hash: str  # SHA-256 of sorted JSON args
    timestamp: float
    result: str  # "ok", "error", "interrupted"


class ToolCallLoopGuard:
    """Detects when the same tool call repeats too many times."""

    def __init__(
        self,
        window_size: int = 20,
        warning_threshold: int = 5,
        block_threshold: int = 8,
    ):
        self.window_size = window_size
        self.warning_threshold = warning_threshold
        self.block_threshold = block_threshold
        self._calls: deque[ToolCallHash] = deque(maxlen=window_size)
        self._phase: str = "normal"

    def _hash_args(self, args: dict[str, Any]) -> str:
        """SHA-256 hash of sorted JSON args."""
        sorted_json = json.dumps(args, sort_keys=True, default=str)
        return hashlib.sha256(sorted_json.encode()).hexdigest()[:16]

    def record_call(self, tool_name: str, args: dict[str, Any], result: str = "ok") -> dict[str, Any]:
        """Record a tool call and check for loops."""
        arg_hash = self._hash_args(args)
        call = ToolCallHash(tool_name=tool_name, arg_hash=arg_hash, timestamp=time.time(), result=result)
        self._calls.append(call)

        identical = sum(1 for c in self._calls if c.tool_name == tool_name and c.arg_hash == arg_hash)

        if identical >= self.block_threshold:
            self._phase = "blocked"
            return {
                "phase": "blocked",
                "count": identical,
                "message": f"BLOCKED: Same tool '{tool_name}' repeated {identical} times. Stop and change approach.",
                "blocked": True,
                "suggestion": f"You've called '{tool_name}' {identical} times with same args. Check preconditions, try different approach, or ask user.",
            }

        if identical >= self.warning_threshold:
            self._phase = "warning"
            return {
                "phase": "warning",
                "count": identical,
                "message": f"WARNING: Same tool '{tool_name}' repeated {identical} times. Consider changing approach.",
                "blocked": False,
                "suggestion": f"You've called '{tool_name}' {identical} times with same args. If not working, try different approach or ask user.",
            }

        if self._phase != "normal":
            self._phase = "normal"

        return {
            "phase": "normal",
            "count": identical,
            "message": f"Tool call '{tool_name}' ({identical} in window)",
            "blocked": False,
            "suggestion": None,
        }

    def reset(self):
        self._calls.clear()
        self._phase = "normal"


_guard: Optional[ToolCallLoopGuard] = None


def get_guard() -> ToolCallLoopGuard:
    global _guard
    if _guard is None:
        _guard = ToolCallLoopGuard()
    return _guard


def reset_guard():
    global _guard
    _guard = None
