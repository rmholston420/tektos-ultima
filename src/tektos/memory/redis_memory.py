"""Redis-backed Sensory and Working Memory tiers.

Sensory Memory (100ms-4s):
- Redis Streams for event buffer (high throughput, append-only)
- TTL-based auto-decay (Redis EXPIRE)
- Attention scores stored as stream entry fields

Working Memory (seconds-minutes, 7±2 items):
- Redis Sorted Sets by significance score (Miller's Law capacity)
- Hash structures for metadata
- Priority-based eviction when at capacity

Both tiers use a single Redis connection with namespace separation.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

# Redis optional import — graceful degradation if not installed
# pyright: reportMissingImports=false
try:
    import redis as _redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    _redis = None


class RedisMemoryConfig(BaseModel):
    """Configuration for Redis-backed memory tiers."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    decode_responses: bool = True
    
    # Sensory tier settings
    sensory_key_prefix: str = "tektos:sensory"
    sensory_stream_max_len: int = 1000
    sensory_ttl_seconds: float = 4.0
    
    # Working tier settings
    working_key_prefix: str = "tektos:working"
    working_capacity: int = 7
    working_ttl_seconds: float = 300.0


class RedisSensoryMemory:
    """Redis-backed sensory memory tier.
    
    Uses Redis Streams for high-throughput append-only storage
    with automatic TTL-based decay.
    """
    
    def __init__(self, config: RedisMemoryConfig | None = None) -> None:
        self.config = config or RedisMemoryConfig()
        self._client: Any = None
        self._stream_key = f"{self.config.sensory_key_prefix}:stream"
    
    def connect(self) -> None:
        """Establish Redis connection."""
        if not REDIS_AVAILABLE:
            raise RuntimeError(
                "redis-py not installed. Install with: pip install redis"
            )
        import redis as redis_module
        
        self._client = redis_module.Redis(
            host=self.config.host,
            port=self.config.port,
            db=self.config.db,
            password=self.config.password,
            decode_responses=self.config.decode_responses,
        )
    
    def add(
        self,
        content: str,
        attention_score: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add a sensory memory entry to Redis Stream."""
        if self._client is None:
            self.connect()
        
        client = self._client  # narrow type
        
        entry_id = client.xadd(
            self._stream_key,
            {
                "content": content,
                "attention": str(attention_score),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": json.dumps(metadata or {}),
            },
            maxlen=self.config.sensory_stream_max_len,
            approximate=True,
        )
        
        client.expire(self._stream_key, int(self.config.sensory_ttl_seconds * 10))
        
        return entry_id.decode() if isinstance(entry_id, bytes) else entry_id
    
    def get_recent(self, count: int = 50) -> list[dict[str, Any]]:
        """Get recent sensory memories from stream.
        
        Args:
            count: Number of entries to retrieve.
        
        Returns:
            List of memory dicts with content, attention, metadata.
        """
        if self._client is None:
            return []
        
        # XREVRANGE gets latest entries first
        entries = self._client.xrevrange(
            self._stream_key,
            count=count,
        )
        
        memories = []
        for entry_id, fields in entries:
            memories.append({
                "id": entry_id.decode() if isinstance(entry_id, bytes) else entry_id,
                "content": fields.get("content", ""),
                "attention_score": float(fields.get("attention", 0)),
                "timestamp": fields.get("timestamp", ""),
                "metadata": json.loads(fields.get("metadata", "{}")),
            })
        
        return memories
    
    def get_high_attention(self, threshold: float = 0.8) -> list[dict[str, Any]]:
        """Get sensory memories with attention above threshold.
        
        These are candidates for transfer to working memory.
        """
        all_memories = self.get_recent(100)
        return [m for m in all_memories if m["attention_score"] >= threshold]
    
    def decay(self) -> int:
        """Remove expired entries. Redis handles TTL automatically,
        but this returns count of entries that would be cleaned.
        
        Returns:
            Number of entries that could be removed (approximate).
        """
        if self._client is None:
            return 0
        
        # Trim stream to max length (Redis does this approximately)
        current_len = self._client.xlen(self._stream_key)
        self._client.xtrim(self._stream_key, self.config.sensory_stream_max_len, approximate=True)
        removed = current_len - self._client.xlen(self._stream_key)
        
        return max(0, removed)
    
    def get_all(self) -> list[dict[str, Any]]:
        """Get all sensory memories (for backup/serialization)."""
        return self.get_recent(1000)


class RedisWorkingMemory:
    """Redis-backed working memory tier.
    
    Uses Sorted Sets for priority-based storage (Miller's Law: 7±2 items).
    Hash structures store metadata for each entry.
    """
    
    def __init__(self, config: RedisMemoryConfig | None = None) -> None:
        self.config = config or RedisMemoryConfig()
        self._client: Any = None
        self._sorted_set_key = f"{self.config.working_key_prefix}:set"
        self._hash_prefix = f"{self.config.working_key_prefix}:entry"
    
    def connect(self) -> None:
        """Establish Redis connection."""
        if not REDIS_AVAILABLE or _redis is None:
            raise RuntimeError(
                "redis-py not installed. Install with: pip install redis"
            )
        self._client = _redis.Redis(
            host=self.config.host,
            port=self.config.port,
            db=self.config.db,
            password=self.config.password,
            decode_responses=self.config.decode_responses,
        )
    
    def add(
        self,
        content: str,
        significance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add a working memory entry.
        
        Args:
            content: The memory content.
            significance: 0.0-1.0, used for sorted set score.
            metadata: W5H1M fields and other metadata.
        
        Returns:
            Entry ID.
        """
        if self._client is None:
            self.connect()
        
        entry_id = f"mem-{uuid.uuid4().hex[:8]}"
        
        # Add to sorted set (score = significance)
        self._client.zadd(
            self._sorted_set_key,
            {entry_id: significance},
        )
        
        # Store metadata in hash
        self._client.hset(
            f"{self._hash_prefix}:{entry_id}",
            mapping={
                "content": content,
                "significance": str(significance),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": json.dumps(metadata or {}),
            },
        )
        
        # Set TTL on hash for auto-decay
        self._client.expire(
            f"{self._hash_prefix}:{entry_id}",
            int(self.config.working_ttl_seconds),
        )
        
        # Enforce capacity — remove lowest significance items
        self._enforce_capacity()
        
        return entry_id
    
    def get_all(self) -> list[dict[str, Any]]:
        """Get all working memory entries sorted by significance.
        
        Returns:
            List of memory dicts sorted by significance (highest first).
        """
        if self._client is None:
            return []
        
        # ZREVRANGE gets highest scores first
        member_ids = self._client.zrevrange(self._sorted_set_key, 0, -1)
        
        memories = []
        for member_id in member_ids:
            mid = member_id.decode() if isinstance(member_id, bytes) else member_id
            fields = self._client.hgetall(f"{self._hash_prefix}:{mid}")
            
            if fields:
                memories.append({
                    "id": mid,
                    "content": fields.get("content", ""),
                    "significance": float(fields.get("significance", 0)),
                    "timestamp": fields.get("timestamp", ""),
                    "metadata": json.loads(fields.get("metadata", "{}")),
                })
        
        return memories
    
    def remove(self, entry_id: str) -> bool:
        """Remove a working memory entry.
        
        Args:
            entry_id: The entry to remove.
        
        Returns:
            True if removed, False if not found.
        """
        if self._client is None:
            return False
        
        self._client.zrem(self._sorted_set_key, entry_id)
        self._client.delete(f"{self._hash_prefix}:{entry_id}")
        return True
    
    def _enforce_capacity(self) -> None:
        """Remove lowest significance entries if at capacity."""
        if self._client is None:
            return
        
        current_count = self._client.zcard(self._sorted_set_key)
        
        if current_count > self.config.working_capacity:
            # Remove lowest scoring entries
            to_remove = current_count - self.config.working_capacity
            # ZRANGE gets lowest scores first
            low_members = self._client.zrange(
                self._sorted_set_key, 0, to_remove - 1
            )
            
            for member in low_members:
                mid = member.decode() if isinstance(member, bytes) else member
                self._client.zrem(self._sorted_set_key, mid)
                self._client.delete(f"{self._hash_prefix}:{mid}")
    
    def decay(self) -> int:
        """Remove expired entries. Returns count removed.
        
        Redis TTL handles this automatically, but we track the count.
        """
        if self._client is None:
            return 0
        
        # ZREMRANGEBYSCORE removes entries with score < 0 (expired/removed)
        # Redis TTL handles actual expiry, this is a no-op unless we manually invalidate
        current_count = self._client.zcard(self._sorted_set_key)
        return 0  # TTL handles this automatically
