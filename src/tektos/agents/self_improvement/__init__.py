"""Self-improvement loop module.

Phase 6: Wire SynthesisEngine output back into Planner's next spec.
"""

from .loop_orchestrator import LoopCycle, SelfImprovementLoop

__all__ = ["SelfImprovementLoop", "LoopCycle"]
