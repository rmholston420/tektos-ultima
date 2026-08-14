"""PostgreSQL-backed Long-term and Procedural Memory tiers.

Long-term Memory (days-permanent):
- PostgreSQL with JSONB columns for flexible W5H1M metadata
- pgvector extension for semantic similarity search
- Indexes on tier, hemisphere, novelty_score, timestamp

Procedural Memory (permanent, skills/wisdom):
- PostgreSQL with graph-like edge tables for skill relationships
- Full-text search on content via tsvector
- Skill ID indexing for quick retrieval

Both tiers share a single connection pool with table-based separation.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

# PostgreSQL optional import — graceful degradation
# pyright: reportMissingImports=false, reportPossiblyUnboundVariable=false, reportOptionalMemberAccess=false
try:
    import psycopg2 as _psycopg2
    from psycopg2.extras import RealDictCursor, Json
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    _psycopg2 = None
    Json = None


class PostgresMemoryConfig(BaseModel):
    """Configuration for PostgreSQL-backed memory tiers."""
    
    host: str = "localhost"
    port: int = 5432
    database: str = "tektos"
    user: str = "tektos"
    password: Optional[str] = None
    pool_size: int = 5
    
    # Table names
    long_term_table: str = "tektos_long_term_memory"
    procedural_table: str = "tektos_procedural_memory"


class PostgresLongTermMemory:
    """PostgreSQL-backed long-term memory tier.
    
    Uses JSONB for metadata, pgvector for semantic search.
    """
    
    def __init__(self, config: PostgresMemoryConfig | None = None) -> None:
        self.config = config or PostgresMemoryConfig()
        self._conn: Any = None
    
    def connect(self) -> None:
        """Establish PostgreSQL connection and ensure tables exist."""
        if not POSTGRES_AVAILABLE:
            raise RuntimeError(
                "psycopg2 not installed. Install with: pip install psycopg2-binary"
            )
        
        import psycopg2
        self._conn = psycopg2.connect(
            host=self.config.host,
            port=self.config.port,
            dbname=self.config.database,
            user=self.config.user,
            password=self.config.password,
            cursor_factory=RealDictCursor,
        )
        self._ensure_tables()
    
    def _ensure_tables(self) -> None:
        """Create long-term memory table if it doesn't exist."""
        cursor = self._conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.config.long_term_table} (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                tier TEXT DEFAULT 'long_term',
                hemisphere TEXT DEFAULT 'left',
                is_novel BOOLEAN DEFAULT FALSE,
                novelty_score REAL DEFAULT 0.0,
                timestamp TEXT NOT NULL,
                expires_at TEXT,
                source_tier TEXT,
                destination_tier TEXT,
                who TEXT DEFAULT '',
                what TEXT DEFAULT '',
                where TEXT DEFAULT '',
                why TEXT DEFAULT '',
                how TEXT DEFAULT '',
                metadata JSONB DEFAULT '{{}}'::jsonb
            );
            
            CREATE INDEX IF NOT EXISTS idx_lt_hemisphere 
                ON {self.config.long_term_table}(hemisphere);
            CREATE INDEX IF NOT EXISTS idx_lt_novelty 
                ON {self.config.long_term_table}(novelty_score DESC)
                WHERE is_novel = TRUE;
            CREATE INDEX IF NOT EXISTS idx_lt_timestamp 
                ON {self.config.long_term_table}(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_lt_metadata 
                ON {self.config.long_term_table} USING GIN(metadata);
        """)
        self._conn.commit()
    
    def add(
        self,
        content: str,
        hemisphere: str = "right",
        is_novel: bool = False,
        novelty_score: float = 0.0,
        metadata: dict[str, Any] | None = None,
        **w5h1m: str,
    ) -> str:
        """Add a long-term memory entry.
        
        Args:
            content: The memory content.
            hemisphere: 'left' or 'right'.
            is_novel: Whether this is genuine novelty.
            novelty_score: 0.0-1.0.
            metadata: W5H1M fields and extras.
            **w5h1m: Explicit who/what/where/why/how.
        
        Returns:
            Entry ID.
        """
        if self._conn is None:
            self.connect()
        
        cursor = self._conn.cursor()
        entry_id = f"lt-{__import__('uuid').uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        
        # Merge metadata and w5h1m
        meta = {**(metadata or {}), **{k: v for k, v in w5h1m.items() if v}}
        
        cursor.execute(f"""
            INSERT INTO {self.config.long_term_table}
                (id, content, hemisphere, is_novel, novelty_score,
                 timestamp, metadata, who, what, where, why, how)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            entry_id, content, hemisphere, is_novel, novelty_score,
            now, meta.get('who', ''), meta.get('what', ''),
            meta.get('where', ''), meta.get('why', ''),
            meta.get('how', ''), json.dumps(meta),
        ))
        self._conn.commit()
        
        return entry_id
    
    def get_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get most recent long-term memories."""
        if self._conn is None:
            return []
        
        cursor = self._conn.cursor()
        cursor.execute(f"""
            SELECT id, content, hemisphere, is_novel, novelty_score,
                   timestamp, metadata
            FROM {self.config.long_term_table}
            ORDER BY timestamp DESC
            LIMIT %s
        """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def search_by_similarity(
        self,
        query: str,
        limit: int = 10,
        hemisphere: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search long-term memories by keyword in content/metadata.
        
        Uses ILIKE for case-insensitive text search (pgvector would need embedding generation).
        """
        if self._conn is None:
            return []
        
        cursor = self._conn.cursor()
        query_str = f"%{query}%"
        
        sql = f"""
            SELECT id, content, hemisphere, is_novel, novelty_score,
                   timestamp, metadata
            FROM {self.config.long_term_table}
            WHERE content ILIKE %s OR metadata::text ILIKE %s
        """
        params = [query_str, query_str]
        
        if hemisphere:
            sql += " AND hemisphere = %s"
            params.append(hemisphere)
        
        sql += " ORDER BY timestamp DESC LIMIT %s"
        params.append(str(limit))
        
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_novel_entries(self) -> list[dict[str, Any]]:
        """Get all novelty-flagged entries."""
        if self._conn is None:
            return []
        
        cursor = self._conn.cursor()
        cursor.execute(f"""
            SELECT id, content, hemisphere, novelty_score, timestamp
            FROM {self.config.long_term_table}
            WHERE is_novel = TRUE
            ORDER BY novelty_score DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    def backup(self) -> str:
        """Dump table to SQL dump string for backup.
        
        Returns:
            SQL dump content.
        """
        if self._conn is None:
            return ""
        
        import io
        import psycopg2.sql
        
        output = io.StringIO()
        cursor = self._conn.cursor()
        
        # Copy table data
        cursor.copy_to(
            output,
            self.config.long_term_table,
            columns=['id', 'content', 'hemisphere', 'is_novel', 'novelty_score',
                     'timestamp', 'metadata', 'who', 'what', 'where', 'why', 'how'],
        )
        output.seek(0)
        return output.read()


class PostgresProceduralMemory:
    """PostgreSQL-backed procedural memory tier.
    
    Stores skills, principles, wisdom with relationship edges.
    Uses full-text search for content retrieval.
    """
    
    def __init__(self, config: PostgresMemoryConfig | None = None) -> None:
        self.config = config or PostgresMemoryConfig()
        self._conn: Any = None
    
    def connect(self) -> None:
        """Establish PostgreSQL connection and ensure tables exist."""
        if not POSTGRES_AVAILABLE:
            raise RuntimeError(
                "psycopg2 not installed. Install with: pip install psycopg2-binary"
            )
        
        import psycopg2
        self._conn = psycopg2.connect(
            host=self.config.host,
            port=self.config.port,
            dbname=self.config.database,
            user=self.config.user,
            password=self.config.password,
            cursor_factory=RealDictCursor,
        )
        self._ensure_tables()
    
    def _ensure_tables(self) -> None:
        """Create procedural memory and skill edges tables."""
        cursor = self._conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.config.procedural_table} (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                skill_id TEXT,
                tier TEXT DEFAULT 'procedural',
                hemisphere TEXT DEFAULT 'left',
                is_novel BOOLEAN DEFAULT FALSE,
                novelty_score REAL DEFAULT 0.0,
                timestamp TEXT NOT NULL,
                metadata JSONB DEFAULT '{{}}'::jsonb,
                who TEXT DEFAULT '',
                what TEXT DEFAULT '',
                where TEXT DEFAULT '',
                why TEXT DEFAULT '',
                how TEXT DEFAULT '',
                tsvector_column TSVECTOR
            );
            
            -- Auto-generate tsvector for full-text search
            CREATE OR REPLACE FUNCTION update_tsvector_{self.config.procedural_table.replace('_', '')}()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.tsvector_column := to_tsvector('english', NEW.content || ' ' || COALESCE(NEW.what, ''));
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            
            CREATE TRIGGER tsvector_update_{self.config.procedural_table.replace('_', '')}
                BEFORE INSERT OR UPDATE ON {self.config.procedural_table}
                FOR EACH ROW EXECUTE FUNCTION update_tsvector_{self.config.procedural_table.replace('_', '')}();
            
            CREATE INDEX IF NOT EXISTS idx_proc_skill_id 
                ON {self.config.procedural_table}(skill_id);
            CREATE INDEX IF NOT EXISTS idx_proc_hemisphere 
                ON {self.config.procedural_table}(hemisphere);
            CREATE INDEX IF NOT EXISTS idx_proc_fts 
                ON {self.config.procedural_table} USING GIN(tsvector_column);
            
            -- Skill edges table for relationship graph
            CREATE TABLE IF NOT EXISTS tektos_skill_edges (
                from_id TEXT NOT NULL REFERENCES {self.config.procedural_table}(id),
                to_id TEXT NOT NULL REFERENCES {self.config.procedural_table}(id),
                edge_type TEXT NOT NULL DEFAULT 'related',
                strength REAL DEFAULT 0.5,
                PRIMARY KEY (from_id, to_id)
            );
        """)
        self._conn.commit()
    
    def add(
        self,
        content: str,
        skill_id: str | None = None,
        hemisphere: str = "left",
        metadata: dict[str, Any] | None = None,
        **w5h1m: str,
    ) -> str:
        """Add a procedural memory entry (skill/principle/wisdom).
        
        Args:
            content: The procedural content.
            skill_id: Optional skill identifier.
            hemisphere: 'left' or 'right'.
            metadata: Additional fields.
            **w5h1m: Explicit W5H1M fields.
        
        Returns:
            Entry ID.
        """
        if self._conn is None:
            self.connect()
        
        cursor = self._conn.cursor()
        entry_id = f"proc-{__import__('uuid').uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        
        meta = {**(metadata or {}), **{k: v for k, v in w5h1m.items() if v}}
        
        cursor.execute(f"""
            INSERT INTO {self.config.procedural_table}
                (id, content, skill_id, hemisphere, timestamp, metadata,
                 who, what, where, why, how)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            entry_id, content, skill_id, hemisphere, now,
            json.dumps(meta), meta.get('who', ''), meta.get('what', ''),
            meta.get('where', ''), meta.get('why', ''), meta.get('how', ''),
        ))
        self._conn.commit()
        
        return entry_id
    
    def add_skill_edge(self, from_id: str, to_id: str, edge_type: str = "related", strength: float = 0.5) -> None:
        """Add a relationship edge between two procedural memories.
        
        Args:
            from_id: Source skill/memories ID.
            to_id: Target skill/memory ID.
            edge_type: Type of relationship (related, depends_on, enhances, etc.).
            strength: Edge weight 0.0-1.0.
        """
        if self._conn is None:
            self.connect()
        
        cursor = self._conn.cursor()
        cursor.execute(f"""
            INSERT INTO tektos_skill_edges (from_id, to_id, edge_type, strength)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (from_id, to_id) DO UPDATE SET edge_type = %s, strength = %s
        """, (from_id, to_id, edge_type, strength, edge_type, strength))
        self._conn.commit()
    
    def get_by_skill_id(self, skill_id: str) -> list[dict[str, Any]]:
        """Get all procedural memories for a skill."""
        if self._conn is None:
            return []
        
        cursor = self._conn.cursor()
        cursor.execute(f"""
            SELECT id, content, skill_id, hemisphere, timestamp, metadata
            FROM {self.config.procedural_table}
            WHERE skill_id = %s
            ORDER BY timestamp DESC
        """, (skill_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_all(self) -> list[dict[str, Any]]:
        """Get all procedural memories."""
        if self._conn is None:
            return []
        
        cursor = self._conn.cursor()
        cursor.execute(f"""
            SELECT id, content, skill_id, hemisphere, timestamp, metadata
            FROM {self.config.procedural_table}
            ORDER BY timestamp DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    def search_skills(self, query: str) -> list[dict[str, Any]]:
        """Full-text search across procedural memory."""
        if self._conn is None:
            return []
        
        cursor = self._conn.cursor()
        cursor.execute(f"""
            SELECT id, content, skill_id, hemisphere, timestamp, metadata
            FROM {self.config.procedural_table}
            WHERE tsvector_column @@ plainto_tsquery('english', %s)
            ORDER BY tsvector_column @@ plainto_tsquery('english', %s) DESC
            LIMIT 20
        """, (query, query))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_related(self, entry_id: str, edge_type: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        """Find related procedural memories via skill edges."""
        if self._conn is None:
            return []
        
        cursor = self._conn.cursor()
        
        sql = f"""
            SELECT p.id, p.content, p.skill_id, p.hemisphere, p.timestamp, p.metadata
            FROM {self.config.procedural_table} p
            JOIN tektos_skill_edges e ON p.id = e.to_id
            WHERE e.from_id = %s
        """
        params: list[Any] = [entry_id]
        
        if edge_type:
            sql += " AND e.edge_type = %s"
            params.append(edge_type)
        
        sql += " ORDER BY e.strength DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def backup(self) -> str:
        """Dump procedural memory to SQL dump string."""
        import io
        
        if self._conn is None:
            return ""
        
        output = io.StringIO()
        cursor = self._conn.cursor()
        
        cursor.copy_to(
            output,
            self.config.procedural_table,
            columns=['id', 'content', 'skill_id', 'hemisphere', 'timestamp', 'metadata'],
        )
        output.seek(0)
        return output.read()
