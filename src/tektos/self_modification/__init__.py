"""Self-modification subsystem — Tektos expands its own tests and GUI when it modifies itself.

Modules:
- self_test_expander: Analyzes code changes and generates/extends test suites
- self_gui_expander: Generates/updates GUI components when backend changes
"""

from __future__ import annotations

from .self_test_expander import DiffScope, SelfTestExpander, TestGenerationPlan
from .self_gui_expander import GUIChange, GUIExpansionPlan, SelfGUIExpander

__all__ = [
    "SelfTestExpander",
    "SelfGUIExpander",
    "DiffScope",
    "TestGenerationPlan",
    "GUIChange",
    "GUIExpansionPlan",
]
