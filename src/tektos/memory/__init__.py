"""Memory system — 4-tier architecture with database backends.

Tiers:
- Sensory (100ms-4s): Redis Streams + TTL
- Working (seconds-minutes, 7±2 items): Redis Sorted Sets + Hashes
- Long-term (days-permanent): PostgreSQL + JSONB + pgvector
- Procedural (permanent, skills/wisdom): Neo4j/DozerDB + Graph relationships

Backup scheduler covers all databases with retention policy.
"""

from .backup_scheduler import (
    BackupConfig,
    BackupRecord,
    BackupScheduler,
)
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
from .neo4j_memory import Neo4jMemoryConfig, Neo4jProceduralMemory
from .postgres_memory import (
    PostgresLongTermMemory,
    PostgresMemoryConfig,
)
from .redis_memory import RedisMemoryConfig, RedisSensoryMemory, RedisWorkingMemory

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
    # Redis backends
    "RedisMemoryConfig",
    "RedisSensoryMemory",
    "RedisWorkingMemory",
    # Postgres backends
    "PostgresMemoryConfig",
    "PostgresConfig",
    "PostgresLongTermMemory",
    "PostgresProceduralMemory",
    # Neo4j/DozerDB backend
    "Neo4jMemoryConfig",
    "Neo4jProceduralMemory",
    # Backup scheduler
    "BackupConfig",
    "BackupRecord",
    "BackupScheduler",
]
