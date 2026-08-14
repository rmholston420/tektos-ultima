"""Memory system — 4-tier architecture modeled on the human brain.

Tiers:
1. Sensory (100ms - 4s) — Raw perception buffer
2. Working (seconds - minutes) — Active cognition workspace (7±2 items)
3. Long-term (days - permanent) — Knowledge repository
4. Procedural (permanent) — Skills, wisdom, encoded patterns

Bicameral: left hemisphere = operative (S1), right hemisphere = speculative (S4)
Creativity = Generation of Novelty (McKenna)

Reflection:
- Active contemplation/meditation = deliberate self-examination
- Passive dreamtime = background latent pattern emergence
- Both are forms of periodic reflection
- Direct experience > inference (yogic principle)
"""

from src.tektos.memory.memory_system import (
    DreamResult,
    DreamState,
    DreamtimeEngine,
    Hemisphere,
    MemoryEntry,
    MemorySystem,
    MemoryTier,
    TierConfig,
)
from src.tektos.memory.reflection_engine import (
    ReflectionEngine,
    ReflectionInsight,
    ReflectionState,
)

__all__ = [
    "DreamResult",
    "DreamState",
    "DreamtimeEngine",
    "Hemisphere",
    "MemoryEntry",
    "MemorySystem",
    "MemoryTier",
    "ReflectionEngine",
    "ReflectionInsight",
    "ReflectionState",
    "TierConfig",
]
