"""Memory system — 4-tier architecture with database backends.

Tiers:
- Sensory (100ms-4s): Redis Streams + TTL (optional)
- Working (seconds-minutes, 7±2 items): Redis Sorted Sets + Hashes (optional)
- Long-term (days-permanent): PostgreSQL + JSONB + pgvector (optional)
- Procedural (permanent, skills/wisdom): Neo4j/DozerDB + Graph relationships (optional)

Fallback: SQLite persistence (always available) + FileBasedMemory (CLAUDE.md style).
Backup scheduler covers all databases with retention policy.
"""

from .memory_system import (
    DreamResult,
    DreamState,
    DreamtimeEngine,
    Hemisphere,
    MemoryEntry,
    MemorySystem,
    MemoryTier,
    TierConfig,
)
from .persistence import MemoryPersistence
from .file_based_memory import FileBasedMemory
from .backup_scheduler import (
    BackupConfig,
    BackupRecord,
    BackupScheduler,
)

# Optional backends — only import if dependencies are available
try:
    from .redis_memory import RedisMemoryConfig, RedisSensoryMemory, RedisWorkingMemory
    from .redis_memory import REDIS_AVAILABLE
except ImportError:
    REDIS_AVAILABLE = False
    RedisMemoryConfig = None  # type: ignore
    RedisSensoryMemory = None  # type: ignore
    RedisWorkingMemory = None  # type: ignore

try:
    from .postgres_memory import (
        PostgresLongTermMemory,
        PostgresMemoryConfig,
        PostgresProceduralMemory,
    )
    from .postgres_memory import POSTGRES_AVAILABLE
except ImportError:
    POSTGRES_AVAILABLE = False
    PostgresLongTermMemory = None  # type: ignore
    PostgresMemoryConfig = None  # type: ignore
    PostgresProceduralMemory = None  # type: ignore

try:
    from .neo4j_memory import Neo4jMemoryConfig, Neo4jProceduralMemory
    from .neo4j_memory import NEO4J_AVAILABLE
except ImportError:
    NEO4J_AVAILABLE = False
    Neo4jMemoryConfig = None  # type: ignore
    Neo4jProceduralMemory = None  # type: ignore

__all__ = [
    # Memory system
    "MemorySystem",
    "MemoryTier",
    "MemoryEntry",
    "TierConfig",
    "Hemisphere",
    "DreamtimeEngine",
    "DreamState",
    "DreamResult",
    # Persistence
    "MemoryPersistence",
    "FileBasedMemory",
    # Redis backends (optional)
    "REDIS_AVAILABLE",
    "RedisMemoryConfig",
    "RedisSensoryMemory",
    "RedisWorkingMemory",
    # Postgres backends (optional)
    "POSTGRES_AVAILABLE",
    "PostgresMemoryConfig",
    "PostgresLongTermMemory",
    "PostgresProceduralMemory",
    # Neo4j/DozerDB backend (optional)
    "NEO4J_AVAILABLE",
    "Neo4jMemoryConfig",
    "Neo4jProceduralMemory",
    # Backup scheduler
    "BackupConfig",
    "BackupRecord",
    "BackupScheduler",
]
