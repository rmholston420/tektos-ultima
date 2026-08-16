"""4-Tier Memory System — modeled on the human brain's memory architecture.

The brain does NOT have one "memory." It has four distinct systems,
each with different capacity, decay rate, retrieval speed, and function:

1. SENSORY MEMORY (100ms - 4s) — Raw perception buffer
   - Holds every sensory input momentarily
   - Filters to working memory via attention
   - Analogue: WebSocket event stream buffer

2. WORKING / SHORT-TERM MEMORY (seconds - minutes) — Active cognition workspace
   - Holds current task context, conversation thread
   - Limited capacity (7±2 items, Miller's Law)
   - Analogue: Session context, current spec, active plan

3. LONG-TERM MEMORY (days - permanent) — Knowledge repository
   - Declarative: facts, events, concepts (hippocampus-dependent)
   - Episodic: personal experiences, task history
   - Analogue: Hindsight, session DB, Trail

4. PROCEDURAL / SEMANTIC MEMORY (permanent) — Skills, wisdom, encoded patterns
   - Procedural: "how to" — skills, routines, tool calling patterns
   - Semantic: "what is" — principles, axioms, VSM, PRINST
   - Analogue: Skills database, ADRs, PORTING-LEDGER, git history

Each tier has:
- Capacity limit (tokens, entries, time)
- Decay rate (how quickly data fades)
- Retrieval speed (fast → slow)
- Transfer mechanism (when data moves to next tier)

Bicameral Architecture:
The brain is bicameral — left hemisphere (operative, logical, sequential)
vs right hemisphere (speculative, holistic, contextual).
This maps directly to our operative/speculative dualism:
- Left = S1 Coding Agent (operational execution)
- Right = S4 Planner/Thinker (speculative planning)
- S3 Manager = corpus callosum (integrates both hemispheres)

Creativity = Generation of Novelty (McKenna)
Novelty is NOT recombination. It is genuine emergence — the system
generates something that did not exist before. This happens when:
1. A pattern is recognized that has NO existing skill/structure
2. The Planner generates a spec that introduces new architecture
3. The Manager creates a new archetype → skill pipeline
4. Two existing concepts combine in a way that creates new meaning

Novelty requires:
- Sufficient variety (Ashby's Law: enough internal complexity)
- Bicameral tension (left/right hemisphere cross-talk)
- Safe failure space (can try novel ideas without catastrophic cost)
- Encoding mechanism (novel ideas must be captured before they fade)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import logging
from pydantic import BaseModel, Field


# Import persistence layer here to avoid circular deps
try:
    from .persistence import MemoryPersistence as _MemoryPersistence  # noqa: F401
except ImportError:
    _MemoryPersistence = None  # type: ignore

log = logging.getLogger("tektos.memory")


# ── Memory Tier Types ─────────────────────────────────────────────────────


class MemoryTier(str, Enum):
    """The four memory tiers, ordered by persistence."""

    SENSORY = "sensory"        # 100ms - 4s
    WORKING = "working"        # seconds - minutes
    LONG_TERM = "long_term"    # days - permanent
    PROCEDURAL = "procedural"  # permanent (skills, wisdom)


class Hemisphere(str, Enum):
    """Bicameral hemisphere — left vs right brain."""

    LEFT = "left"      # Operative, logical, sequential, language
    RIGHT = "right"    # Speculative, holistic, contextual, spatial


# ── Memory Entry ──────────────────────────────────────────────────────────


class MemoryEntry(BaseModel):
    """A single memory entry carrying W5H1M metadata."""

    id: str = Field(default_factory=lambda: f"mem-{uuid.uuid4().hex[:8]}")
    content: str = Field(..., description="The memory content")
    tier: MemoryTier = Field(..., description="Which memory tier this belongs to")
    hemisphere: Hemisphere = Field(
        default=Hemisphere.LEFT,
        description="Which hemisphere generated this memory (left=operative, right=speculative)",
    )
    is_novel: bool = Field(
        default=False,
        description="Is this a genuine novelty (not recombination of existing patterns)?",
    )
    novelty_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How novel is this entry? 0 = purely recombined, 1 = pure novelty",
    )
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str | None = Field(
        default=None,
        description="When this memory expires/decays (sensory & working only)",
    )
    source_tier: MemoryTier | None = Field(
        default=None,
        description="Which tier this was transferred from (None if created at this tier)",
    )
    destination_tier: MemoryTier | None = Field(
        default=None,
        description="Which tier this was transferred to (None if stays at this tier)",
    )
    # W5H1M metadata
    who: str = Field(default="", description="Who created this memory")
    what: str = Field(default="", description="What event/pattern was encoded")
    where: str = Field(default="", description="Where was this generated")
    when: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="When created")
    why: str = Field(default="", description="Why was this encoded")
    how: str = Field(default="", description="How was this encoded")
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Tier Configuration ────────────────────────────────────────────────────


class TierConfig(BaseModel):
    """Configuration for a single memory tier."""

    tier: MemoryTier
    capacity: int = Field(..., description="Maximum entries in this tier")
    decay_seconds: float = Field(..., description="Seconds before entries decay")
    retrieval_speed_ms: float = Field(..., description="Average retrieval time in ms")
    transfer_threshold: float = Field(
        default=0.7,
        description="Score threshold for transferring to next tier",
    )


# ── 4-Tier Memory System ─────────────────────────────────────────────────


class MemorySystem:
    """Four-tier memory system modeled on the human brain.

    Tiers are independent but connected via transfer mechanisms:
    - Sensory → Working: via attention mechanism
    - Working → Long-term: via encoding (repetition, significance, novelty)
    - Long-term → Procedural: via skill/wisdom encoding

    Bicameral integration:
    - Left hemisphere memories are operative (execution, language, logic)
    - Right hemisphere memories are speculative (design, context, pattern)
    - Novelty generation requires cross-hemispheric tension

    Attributes:
        tiers: Dictionary mapping tier names to memory entry lists.
        configs: Configuration for each tier.
        transfer_history: Records of all memory transfers.
        novelty_count: Total novelty entries generated.
    """

    # Tier configurations (modeled on human brain)
    DEFAULT_CONFIGS = {
        MemoryTier.SENSORY: TierConfig(
            tier=MemoryTier.SENSORY,
            capacity=1000,  # High capacity, fleeting
            decay_seconds=4.0,  # 100ms - 4s
            retrieval_speed_ms=10.0,  # Near-instant
            transfer_threshold=0.8,  # Only highly attended items transfer
        ),
        MemoryTier.WORKING: TierConfig(
            tier=MemoryTier.WORKING,
            capacity=7,  # Miller's Law: 7±2 items
            decay_seconds=300.0,  # 5 minutes
            retrieval_speed_ms=50.0,  # Fast
            transfer_threshold=0.6,  # Significant items transfer
        ),
        MemoryTier.LONG_TERM: TierConfig(
            tier=MemoryTier.LONG_TERM,
            capacity=10000,  # Large capacity
            decay_seconds=0.0,  # No decay (permanent unless removed)
            retrieval_speed_ms=500.0,  # Moderate
            transfer_threshold=0.0,  # Does not transfer further
        ),
        MemoryTier.PROCEDURAL: TierConfig(
            tier=MemoryTier.PROCEDURAL,
            capacity=1000,  # Skills + wisdom + ADRs
            decay_seconds=0.0,  # No decay
            retrieval_speed_ms=100.0,  # Fast (cached)
            transfer_threshold=0.0,  # Does not transfer further
        ),
    }

    def __init__(self, persistence: Any | None = None) -> None:
        self.tiers: dict[MemoryTier, list[MemoryEntry]] = {
            tier: [] for tier in MemoryTier
        }
        # Deep-copy configs so tests can't mutate the shared class default
        import copy
        self.configs = copy.deepcopy(self.DEFAULT_CONFIGS)
        self.transfer_history: list[dict[str, Any]] = []
        self.novelty_count: int = 0
        # Persistence layer
        if persistence is not None:
            self.persistence = persistence
        else:
            if _MemoryPersistence is not None:
                self.persistence = _MemoryPersistence()
            else:
                self.persistence = None  # type: ignore
        # Load persisted entries into memory on init
        self._load_from_persistence()
        # Start background decay scheduler
        if self.persistence:
            self.persistence.start_decay_scheduler(interval=30.0)
        # Dreamtime engine (passive reflection) — initialized last to avoid circular deps
        self.dreamtime: DreamtimeEngine = DreamtimeEngine(self)

    def _load_from_persistence(self) -> None:
        """Load all persistent tiers from SQLite into memory."""
        if not self.persistence:
            return
        try:
            # Working memory (up to capacity)
            working = self.persistence.load_working(limit=self.configs[MemoryTier.WORKING].capacity)
            for w in working:
                self.tiers[MemoryTier.WORKING].append(self._dict_to_entry(w))

            # Long-term memory (recent entries)
            long_term = self.persistence.load_long_term(limit=100)
            for lt in long_term:
                self.tiers[MemoryTier.LONG_TERM].append(self._dict_to_entry(lt))

            # Procedural memory
            procedural = self.persistence.load_procedural()
            for p in procedural:
                self.tiers[MemoryTier.PROCEDURAL].append(self._dict_to_entry(p))

            # Count novel entries
            for tier in self.tiers.values():
                self.novelty_count += sum(1 for e in tier if e.is_novel)

            # Load transfer history
            transfers = self.persistence.get_transfer_history(limit=200)
            self.transfer_history = transfers

            log.info(f"Loaded {len(working)} working, {len(long_term)} long-term, {len(procedural)} procedural memories")
        except Exception as e:
            log.warning(f"Failed to load persisted memory: {e}")

    @staticmethod
    def _dict_to_entry(d: dict[str, Any]) -> MemoryEntry:
        """Convert a persisted dict back to MemoryEntry."""
        return MemoryEntry(
            id=d["id"],
            content=d["content"],
            tier=d.get("tier", MemoryTier.LONG_TERM),
            hemisphere=d.get("hemisphere", "left"),
            is_novel=d.get("is_novel", False),
            novelty_score=d.get("novelty_score", 0.0),
            timestamp=d.get("timestamp", ""),
            expires_at=d.get("expires_at"),
            source_tier=d.get("source_tier"),
            destination_tier=d.get("destination_tier"),
            who=d.get("who", ""),
            what=d.get("what", ""),
            where=d.get("where", ""),
            when=d.get("when", ""),
            why=d.get("why", ""),
            how=d.get("how", ""),
            metadata=d.get("metadata", {}),
        )

    def _save_to_persistence(self, entry: MemoryEntry) -> None:
        """Save an entry to the SQLite persistence layer."""
        if not self.persistence:
            return
        try:
            if entry.tier == MemoryTier.WORKING:
                self.persistence.save_working({
                    "id": entry.id,
                    "content": entry.content,
                    "hemisphere": entry.hemisphere.value,
                    "is_novel": entry.is_novel,
                    "novelty_score": entry.novelty_score,
                    "timestamp": entry.timestamp,
                    "expires_at": entry.expires_at,
                    "source_tier": entry.source_tier.value if entry.source_tier else None,
                    "destination_tier": entry.destination_tier.value if entry.destination_tier else None,
                    "who": entry.who,
                    "what": entry.what,
                    "where": entry.where,
                    "when": entry.when,
                    "why": entry.why,
                    "how": entry.how,
                    "metadata": entry.metadata,
                })
            elif entry.tier == MemoryTier.LONG_TERM:
                self.persistence.save_long_term({
                    "id": entry.id,
                    "content": entry.content,
                    "hemisphere": entry.hemisphere.value,
                    "is_novel": entry.is_novel,
                    "novelty_score": entry.novelty_score,
                    "timestamp": entry.timestamp,
                    "expires_at": entry.expires_at,
                    "source_tier": entry.source_tier.value if entry.source_tier else None,
                    "destination_tier": entry.destination_tier.value if entry.destination_tier else None,
                    "who": entry.who,
                    "what": entry.what,
                    "where": entry.where,
                    "when": entry.when,
                    "why": entry.why,
                    "how": entry.how,
                    "metadata": entry.metadata,
                })
            elif entry.tier == MemoryTier.PROCEDURAL:
                self.persistence.save_procedural({
                    "id": entry.id,
                    "content": entry.content,
                    "hemisphere": entry.hemisphere.value,
                    "is_novel": entry.is_novel,
                    "novelty_score": entry.novelty_score,
                    "timestamp": entry.timestamp,
                    "expires_at": entry.expires_at,
                    "source_tier": entry.source_tier.value if entry.source_tier else None,
                    "destination_tier": entry.destination_tier.value if entry.destination_tier else None,
                    "who": entry.who,
                    "what": entry.what,
                    "where": entry.where,
                    "when": entry.when,
                    "why": entry.why,
                    "how": entry.how,
                    "metadata": entry.metadata,
                })
            # SENSORY is ephemeral — not persisted
        except Exception as e:
            log.warning(f"Failed to persist memory entry {entry.id}: {e}")

    def add(
        self,
        content: str,
        tier: MemoryTier = MemoryTier.SENSORY,
        hemisphere: Hemisphere = Hemisphere.LEFT,
        is_novel: bool = False,
        novelty_score: float = 0.0,
        **kwargs: Any,
    ) -> MemoryEntry:
        """Add an entry to the specified memory tier.

        Args:
            content: The memory content.
            tier: Which tier to store in.
            hemisphere: Which hemisphere generated this.
            is_novel: Is this genuine novelty?
            novelty_score: 0.0 (recombined) to 1.0 (pure novelty).
            **kwargs: Additional metadata (W5H1M fields).

        Returns:
            The created MemoryEntry.

        Raises:
            ValueError: If tier is at capacity.
        """
        config = self.configs[tier]

        # Enforce capacity
        if len(self.tiers[tier]) >= config.capacity:
            raise ValueError(
                f"{tier.value} memory is at capacity ({config.capacity}). "
                f"Remove old entries or increase capacity."
            )

        entry = MemoryEntry(
            content=content,
            tier=tier,
            hemisphere=hemisphere,
            is_novel=is_novel,
            novelty_score=novelty_score,
            **kwargs,
        )

        # Set expiry for non-permanent tiers
        if tier in (MemoryTier.SENSORY, MemoryTier.WORKING):
            expiry = datetime.now(timezone.utc) + timedelta(seconds=config.decay_seconds)
            entry.expires_at = expiry.isoformat()

        self.tiers[tier].append(entry)

        # Persist to SQLite
        self._save_to_persistence(entry)

        # Track novelty
        if is_novel:
            self.novelty_count += 1

        return entry

    def add_sensory(
        self,
        content: str,
        attention_score: float = 1.0,
        is_novel: bool | None = None,
        novelty_score: float | None = None,
        **kwargs: Any,
    ) -> MemoryEntry:
        """Add a sensory memory entry.

        Sensory memories are raw perception buffers. They are fleeting
        and require attention to transfer to working memory.

        Args:
            content: The raw sensory content.
            attention_score: How much attention this received (0.0 - 1.0).
                Only items above transfer_threshold are promoted.
            is_novel: Override for novelty flag. None = auto-detect from attention.
            novelty_score: Override for novelty score. None = auto-detect from attention.
            **kwargs: Additional metadata.

        Returns:
            The created MemoryEntry.
        """
        kwargs.setdefault("why", f"Attention score: {attention_score}")

        # Auto-detect novelty from attention if not explicitly provided
        if is_novel is None:
            is_novel = attention_score > 0.9
        if novelty_score is None:
            novelty_score = attention_score if attention_score > 0.9 else 0.0

        entry = self.add(
            content=content,
            tier=MemoryTier.SENSORY,
            hemisphere=kwargs.pop("hemisphere", Hemisphere.LEFT),
            is_novel=is_novel,
            novelty_score=novelty_score,
            **kwargs,
        )
        # Transfer if attention exceeds threshold
        if attention_score >= self.configs[MemoryTier.SENSORY].transfer_threshold:
            self._transfer_to_working(content, entry, **kwargs)
        return entry

    # Core internal methods
    def _add_working(
        self,
        content: str,
        significance: float = 0.5,
        hemisphere: Hemisphere = Hemisphere.LEFT,
        **kwargs: Any,
    ) -> MemoryEntry:
        """Internal: Add a working memory entry."""
        kwargs.setdefault("why", f"Significance: {significance}")
        entry = self.add(
            content=content,
            tier=MemoryTier.WORKING,
            hemisphere=hemisphere,
            **kwargs,
        )
        if significance >= self.configs[MemoryTier.WORKING].transfer_threshold:
            self._transfer_to_long_term(content, entry, **kwargs)
        return entry

    def _add_long_term(
        self,
        content: str,
        hemisphere: Hemisphere = Hemisphere.RIGHT,
        **kwargs: Any,
    ) -> MemoryEntry:
        """Internal: Add a long-term memory entry."""
        return self.add(
            content=content,
            tier=MemoryTier.LONG_TERM,
            hemisphere=hemisphere,
            **kwargs,
        )

    def _add_procedural(
        self,
        content: str,
        skill_id: str | None = None,
        **kwargs: Any,
    ) -> MemoryEntry:
        """Internal: Add a procedural memory entry."""
        entry = self.add(
            content=content,
            tier=MemoryTier.PROCEDURAL,
            **kwargs,
        )
        if skill_id:
            entry.metadata["skill_id"] = skill_id
        return entry

    # Public aliases matching test expectations
    def add_working_memory(
        self,
        content: str,
        significance: float = 0.5,
        hemisphere: Hemisphere = Hemisphere.LEFT,
        **kwargs: Any,
    ) -> MemoryEntry:
        """Add a working memory entry. Alias for _add_working."""
        return self._add_working(content, significance=significance, hemisphere=hemisphere, **kwargs)

    def add_long_term_memory(
        self,
        content: str,
        hemisphere: Hemisphere = Hemisphere.RIGHT,
        **kwargs: Any,
    ) -> MemoryEntry:
        """Add a long-term memory entry. Alias for _add_long_term."""
        return self._add_long_term(content, hemisphere=hemisphere, **kwargs)

    def add_procedural_memory(
        self,
        content: str,
        skill_id: str | None = None,
        **kwargs: Any,
    ) -> MemoryEntry:
        """Add a procedural memory entry. Alias for _add_procedural."""
        return self._add_procedural(content, skill_id=skill_id, **kwargs)

    def decay_long_term_memory(self) -> int:
        """Long-term memory has no decay. Returns 0."""
        return 0

    def decay_procedural_memory(self) -> int:
        """Procedural memory has no decay. Returns 0."""
        return 0

    def _transfer_to_working(
        self,
        content: str,
        source_entry: MemoryEntry,
        **kwargs: Any,
    ) -> MemoryEntry:
        """Transfer a sensory memory to working memory."""
        entry = self.add(
            content=content,
            tier=MemoryTier.WORKING,
            source_tier=MemoryTier.SENSORY,
            **kwargs,
        )
        self.transfer_history.append({
            "from": MemoryTier.SENSORY,
            "to": MemoryTier.WORKING,
            "entry_id": entry.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return entry

    def _transfer_to_long_term(
        self,
        content: str,
        source_entry: MemoryEntry,
        **kwargs: Any,
    ) -> MemoryEntry:
        """Transfer a working memory to long-term memory."""
        entry = self.add(
            content=content,
            tier=MemoryTier.LONG_TERM,
            source_tier=MemoryTier.WORKING,
            **kwargs,
        )
        self.transfer_history.append({
            "from": MemoryTier.WORKING,
            "to": MemoryTier.LONG_TERM,
            "entry_id": entry.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return entry

    def decay_sensory(self) -> int:
        """Remove expired sensory memories. Returns count removed."""
        now = datetime.now(timezone.utc)
        before = len(self.tiers[MemoryTier.SENSORY])
        self.tiers[MemoryTier.SENSORY] = [
            entry
            for entry in self.tiers[MemoryTier.SENSORY]
            if entry.expires_at is None or datetime.fromisoformat(entry.expires_at) > now
        ]
        return before - len(self.tiers[MemoryTier.SENSORY])

    def decay_working(self) -> int:
        """Remove expired working memories. Returns count removed."""
        now = datetime.now(timezone.utc)
        before = len(self.tiers[MemoryTier.WORKING])
        self.tiers[MemoryTier.WORKING] = [
            entry
            for entry in self.tiers[MemoryTier.WORKING]
            if entry.expires_at is None or datetime.fromisoformat(entry.expires_at) > now
        ]
        return before - len(self.tiers[MemoryTier.WORKING])

    def get_working_memory(self) -> list[MemoryEntry]:
        """Get current working memory entries."""
        return self.tiers[MemoryTier.WORKING]

    def get_recent_long_term(self, limit: int = 20) -> list[MemoryEntry]:
        """Get most recent long-term memory entries."""
        return self.tiers[MemoryTier.LONG_TERM][:limit]

    def get_procedural_memories(self) -> list[MemoryEntry]:
        """Get all procedural memories (skills, principles, wisdom)."""
        return self.tiers[MemoryTier.PROCEDURAL]

    def get_novelty_entries(self) -> list[MemoryEntry]:
        """Get all entries flagged as novelty."""
        return [
            entry
            for tier in self.tiers.values()
            for entry in tier
            if entry.is_novel
        ]

    def get_hemisphere_balance(self) -> dict[str, int]:
        """Get count of memories per hemisphere across all tiers."""
        balance: dict[str, int] = {"left": 0, "right": 0}
        for tier in self.tiers.values():
            for entry in tier:
                balance[entry.hemisphere.value] += 1
        return balance

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the memory system state."""
        return {
            "sensory_count": len(self.tiers[MemoryTier.SENSORY]),
            "working_count": len(self.tiers[MemoryTier.WORKING]),
            "long_term_count": len(self.tiers[MemoryTier.LONG_TERM]),
            "procedural_count": len(self.tiers[MemoryTier.PROCEDURAL]),
            "novelty_count": self.novelty_count,
            "hemisphere_balance": self.get_hemisphere_balance(),
            "transfer_count": len(self.transfer_history),
        }


# ── Dreamtime / Contemplation ─────────────────────────────────────────────


class DreamState(str, Enum):
    """Dreamtime/contemplation states for right-hemisphere processing."""

    IDLE = "idle"                    # Not currently dreaming
    GATHERING = "gathering"          # Collecting memories for processing
    PROCESSING = "processing"        # Right hemisphere cross-pollinating ideas
    INSIGHT_GENERATED = "insight_generated"  # Novel connections discovered
    SAVING = "saving"                # Persisting insights to long-term memory


class DreamResult(BaseModel):
    """A result of dreamtime/contemplation processing."""

    id: str = Field(default_factory=lambda: f"dream-{uuid.uuid4().hex[:8]}")
    source_count: int = Field(..., description="How many memories were processed")
    insight_count: int = Field(..., description="How many novel insights were generated")
    is_novel: bool = Field(default=False, description="Was this genuine novelty?")
    novelty_score: float = Field(default=0.0, ge=0.0, le=1.0)
    insights: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    who: str = Field(default="S4 Planner/Thinker (Right Hemisphere)", description="W5H1M: Who generated these insights")
    what: str = Field(default="", description="W5H1M: What insights were generated")
    where: str = Field(default="right hemisphere (speculative processing)", description="W5H1M: Where generated")
    when: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="W5H1M: When generated")
    why: str = Field(default="Cross-pollinate ideas and generate novelty during contemplation", description="W5H1M: Why processing")
    how: str = Field(default="Right-hemisphere associative processing of long-term memories", description="W5H1M: How processed")
    metadata: dict[str, Any] = Field(default_factory=dict)


class DreamtimeEngine:
    """Dreamtime/contemplation engine — right-hemisphere processing during idle.

    ClaudeBots have a dream function: during idle periods, they review
    conversation history, cross-pollinate ideas, and surface insights
    that were not available during active conversation.

    This is NOT idle time — it's speculative processing time.

    The dreamtime engine:
    1. Gathers memories from long-term and procedural tiers
    2. Performs associative cross-pollination (right-hemisphere style)
    3. Identifies novel connections between previously unrelated concepts
    4. Generates insights and saves them to long-term memory
    5. Reports results for Manager review

    Dreamtime states:
    - IDLE: Not currently dreaming
    - GATHERING: Collecting memories for processing
    - PROCESSING: Right-hemisphere associative cross-talk
    - INSIGHT_GENERATED: Novel connections discovered
    - SAVING: Persisting insights to long-term memory

    Creativity = Generation of Novelty (McKenna)
    Dreamtime is the system's capacity for genuine creative emergence.
    """

    def __init__(self, memory_system: MemorySystem) -> None:
        self.memory = memory_system
        self.state = DreamState.IDLE
        self.dream_history: list[DreamResult] = []
        self.insight_count: int = 0

    def begin_contemplation(
        self,
        max_memories: int = 50,
        focus_area: str | None = None,
    ) -> list[MemoryEntry]:
        """Begin a dreamtime session.

        Gathers memories from long-term and procedural tiers for
        right-hemisphere associative processing.

        Args:
            max_memories: Maximum memories to gather for processing.
            focus_area: Optional focus area for targeted processing.

        Returns:
            List of gathered memories for processing.
        """
        self.state = DreamState.GATHERING
        gathered: list[MemoryEntry] = []

        # Gather long-term memories (right-hemisphere: holistic, contextual)
        long_term = self.memory.get_recent_long_term(limit=max_memories)
        gathered.extend(long_term)

        # Gather procedural memories (skills, principles, wisdom)
        procedural = self.memory.get_procedural_memories()
        gathered.extend(procedural[:max(1, max_memories // len(procedural) + 1) if procedural else 1])

        # Filter by focus area if specified
        if focus_area:
            gathered = [
                m for m in gathered
                if focus_area.lower() in m.content.lower() or focus_area.lower() in m.what.lower()
            ]

        self.state = DreamState.PROCESSING
        return gathered

    def process_associations(
        self,
        memories: list[MemoryEntry],
    ) -> DreamResult:
        """Process gathered memories through right-hemisphere associative cross-talk.

        This is where creativity happens — the system finds novel connections
        between previously unrelated concepts. The Manager evaluates whether
        the generated novelty is worth encoding.

        Args:
            memories: Memories gathered by begin_contemplation.

        Returns:
            DreamResult with generated insights.
        """
        if not memories:
            return DreamResult(
                source_count=0,
                insight_count=0,
                is_novel=False,
                novelty_score=0.0,
                insights=[],
            )

        # Right-hemisphere associative processing:
        # Find connections between memories that share concepts but have different domains
        insights: list[str] = []

        # Strategy 1: Cross-domain connections (left + right hemisphere)
        left_memories = [m for m in memories if m.hemisphere == Hemisphere.LEFT]
        right_memories = [m for m in memories if m.hemisphere == Hemisphere.RIGHT]

        for left in left_memories[:5]:
            for right in right_memories[:5]:
                if left.what and right.what:
                    # Check for conceptual overlap
                    left_words = set(left.what.lower().split())
                    right_words = set(right.what.lower().split())
                    common = left_words & right_words
                    if common:
                        insight = f"Connection: '{left.content[:80]}' ↔ '{right.content[:80]}' (shared concept: {', '.join(common)})"
                        insights.append(insight)

        # Strategy 2: Novel pattern synthesis
        # Combine multiple memories to generate emergent insights
        if len(memories) >= 3:
            # Take up to 3 memories and synthesize
            sample = memories[:min(3, len(memories))]
            if len(sample) == 3:
                insight = f"Synthesis: '{sample[0].content[:60]}' + '{sample[1].content[:60]}' + '{sample[2].content[:60]}' → emergent pattern"
                insights.append(insight)
            elif len(sample) == 2:
                insight = f"Synthesis: '{sample[0].content[:60]}' + '{sample[1].content[:60]}' → new relationship"
                insights.append(insight)

        # Strategy 3: Gap detection
        # Find what's missing — what questions remain unanswered
        for memory in memories:
            if "unknown" in memory.content.lower() or "?" in memory.content:
                insights.append(f"Gap: Unanswered question — '{memory.content[:80]}'")

        # Evaluate novelty
        is_novel = len(insights) > 0 and any("emergent" in i.lower() or "connection" in i.lower() for i in insights)
        novelty_score = min(1.0, len(insights) * 0.15) if is_novel else 0.0

        self.state = DreamState.INSIGHT_GENERATED

        result = DreamResult(
            source_count=len(memories),
            insight_count=len(insights),
            is_novel=is_novel,
            novelty_score=novelty_score,
            insights=insights,
        )

        return result

    def save_insights(self, result: DreamResult) -> int:
        """Save dreamtime insights to long-term memory.

        The Manager evaluates whether insights should be encoded.
        High-novelty insights are promoted to procedural memory.

        Args:
            result: DreamResult from process_associations.

        Returns:
            Number of insights saved.
        """
        if not result.insights:
            return 0

        saved = 0
        for insight in result.insights:
            # High novelty → procedural memory (permanent)
            # Moderate novelty → long-term memory (persistent)
            if result.novelty_score > 0.5:
                self.memory.add_procedural_memory(
                    content=insight,
                    hemisphere=Hemisphere.RIGHT,
                    is_novel=result.is_novel,
                    novelty_score=result.novelty_score,
                    what=f"dreamtime_insight",
                    where="right hemisphere",
                    why="Creative emergence from associative processing",
                    how="Dreamtime engine",
                )
            else:
                self.memory.add_long_term_memory(
                    content=insight,
                    hemisphere=Hemisphere.RIGHT,
                    is_novel=result.is_novel,
                    novelty_score=result.novelty_score,
                    what=f"dreamtime_insight",
                    where="right hemisphere",
                    why="Creative emergence from associative processing",
                    how="Dreamtime engine",
                )
            saved += 1
            self.insight_count += 1

        self.state = DreamState.SAVING
        return saved

    def run_contemplation(
        self,
        max_memories: int = 50,
        focus_area: str | None = None,
    ) -> DreamResult:
        """Run a complete dreamtime/contemplation cycle.

        Full pipeline:
        1. Gather memories (right-hemisphere: holistic, contextual)
        2. Process associations (cross-pollinate ideas)
        3. Save insights (promote to long-term or procedural)

        Args:
            max_memories: Maximum memories to gather for processing.
            focus_area: Optional focus area for targeted processing.

        Returns:
            DreamResult with generated insights.
        """
        # Step 1: Gather
        memories = self.begin_contemplation(max_memories=max_memories, focus_area=focus_area)

        # Step 2: Process
        result = self.process_associations(memories)

        # Step 3: Save
        self.save_insights(result)

        # Record in dream history
        self.dream_history.append(result)

        # Reset state
        self.state = DreamState.IDLE

        return result

    def get_dream_history(self, limit: int = 10) -> list[DreamResult]:
        """Get recent dreamtime results."""
        return self.dream_history[-limit:]

    def get_summary(self) -> dict[str, Any]:
        """Get dreamtime system summary."""
        return {
            "state": self.state.value,
            "total_dreams": len(self.dream_history),
            "total_insights": self.insight_count,
            "recent_dreams": [
                {
                    "id": d.id,
                    "source_count": d.source_count,
                    "insight_count": d.insight_count,
                    "is_novel": d.is_novel,
                    "novelty_score": d.novelty_score,
                    "timestamp": d.timestamp,
                }
                for d in self.get_dream_history()
            ],
        }
