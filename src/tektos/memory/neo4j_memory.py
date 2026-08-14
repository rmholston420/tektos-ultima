"""DozerDB/Neo4j-backed Procedural Memory tier.

DozerDB is a free, open-source plugin that extends Neo4j Community Edition
with backup/restore capabilities (otherwise locked behind Enterprise).

Procedural Memory (permanent, skills/wisdom):
- Neo4j graph database for skill relationships and concept graphs
- Cypher queries for graph traversal (related skills, dependencies)
- DozerDB plugin enables scheduled dumps and point-in-time restore
- Full-text search via Neo4j text indexing

Connection: bolt://localhost:7687 (standard Neo4j Bolt protocol)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

# Neo4j optional import — graceful degradation
# pyright: reportMissingImports=false, reportOptionalMemberAccess=false
try:
    from neo4j import GraphDatabase as _Neo4j
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    _Neo4j = None


class Neo4jMemoryConfig(BaseModel):
    """Configuration for DozerDB/Neo4j procedural memory."""
    
    host: str = "localhost"
    port: int = 7687
    user: str = "neo4j"
    password: str = "password"
    database: str = "neo4j"
    
    # Backup settings (DozerDB specific)
    backup_dir: str = "/home/rmholston/.tektos/neo4j/backup"
    backup_retention_days: int = 7
    backup_schedule_cron: str = "0 2 * * *"  # daily at 2 AM


class Neo4jProceduralMemory:
    """Neo4j/DozerDB-backed procedural memory tier.
    
    Stores skills, principles, and wisdom as nodes in a graph.
    Relationships between skills enable traversal and dependency analysis.
    DozerDB plugin enables scheduled backup and restore.
    """
    
    def __init__(self, config: Neo4jMemoryConfig | None = None) -> None:
        self.config = config or Neo4jMemoryConfig()
        self._driver: Any = None
    
    def connect(self) -> None:
        """Establish Neo4j connection and ensure constraints/indexes exist."""
        if not NEO4J_AVAILABLE:
            raise RuntimeError(
                "neo4j driver not installed. Install with: pip install neo4j"
            )
        
        import neo4j
        self._driver = neo4j.GraphDatabase.driver(
            f"bolt://{self.config.host}:{self.config.port}",
            auth=(self.config.user, self.config.password),
            database=self.config.database,
        )
        self._driver.verify_connectivity()
        self._ensure_schema()
    
    def _ensure_schema(self) -> None:
        """Create constraints and indexes for optimal querying."""
        with self._driver.session() as session:
            # Unique constraint on procedural memory IDs
            session.run("""
                CREATE CONSTRAINT procedural_id_unique IF NOT EXISTS
                FOR (p:ProceduralMemory) REQUIRE p.id IS UNIQUE
            """)
            
            # Index on skill_id for fast lookups
            session.run("""
                CREATE INDEX procedural_skill_id IF NOT EXISTS
                FOR (p:ProceduralMemory) ON (p.skill_id)
            """)
            
            # Index on hemisphere
            session.run("""
                CREATE INDEX procedural_hemisphere IF NOT EXISTS
                FOR (p:ProceduralMemory) ON (p.hemisphere)
            """)
            
            # Full-text index on content and what
            session.run("""
                CREATE FULLTEXT INDEX procedural_content_search IF NOT EXISTS
                FOR (p:ProceduralMemory) ON EACH [p.content, p.what]
            """)
    
    def add(
        self,
        content: str,
        skill_id: str | None = None,
        hemisphere: str = "left",
        metadata: dict[str, Any] | None = None,
        **w5h1m: str,
    ) -> str:
        """Add a procedural memory node to Neo4j.
        
        Args:
            content: The procedural content (skill/principle/wisdom).
            skill_id: Optional skill identifier for grouping.
            hemisphere: 'left' or 'right'.
            metadata: Additional fields.
            **w5h1m: Explicit W5H1M fields.
        
        Returns:
            Entry ID.
        """
        if self._driver is None:
            self.connect()
        
        entry_id = f"proc-{__import__('uuid').uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        
        meta = {**(metadata or {}), **{k: v for k, v in w5h1m.items() if v}}
        
        with self._driver.session() as session:
            session.run("""
                CREATE (p:ProceduralMemory)
                SET p.id = $id,
                    p.content = $content,
                    p.skill_id = $skill_id,
                    p.hemisphere = $hemisphere,
                    p.timestamp = $timestamp,
                    p.metadata = $metadata,
                    p.who = $who,
                    p.what = $what,
                    p.where = $where,
                    p.why = $why,
                    p.how = $how
                RETURN p.id
            """, id=entry_id, content=content, skill_id=skill_id,
                hemisphere=hemisphere, timestamp=now,
                metadata=json.dumps(meta),
                who=meta.get('who', ''), what=meta.get('what', ''),
                where=meta.get('where', ''), why=meta.get('why', ''),
                how=meta.get('how', ''))
        
        return entry_id
    
    def add_relationship(
        self,
        from_id: str,
        to_id: str,
        edge_type: str = "RELATED_TO",
        strength: float = 0.5,
    ) -> None:
        """Add a relationship edge between two procedural memories.
        
        Args:
            from_id: Source procedural memory ID.
            to_id: Target procedural memory ID.
            edge_type: Relationship type (RELATED_TO, DEPENDS_ON, ENHANCES, etc.).
            strength: Edge weight 0.0-1.0.
        """
        if self._driver is None:
            self.connect()
        
        with self._driver.session() as session:
            session.run("""
                MATCH (a:ProceduralMemory {id: $from_id}),
                      (b:ProceduralMemory {id: $to_id})
                MERGE (a)-[r:REL {type: $edge_type}]->(b)
                SET r.strength = $strength
            """, from_id=from_id, to_id=to_id,
                edge_type=edge_type, strength=strength)
    
    def get_by_skill_id(self, skill_id: str) -> list[dict[str, Any]]:
        """Get all procedural memories for a skill."""
        if self._driver is None:
            return []
        
        with self._driver.session() as session:
            result = session.run("""
                MATCH (p:ProceduralMemory {skill_id: $skill_id})
                RETURN p.id as id, p.content as content,
                       p.skill_id as skill_id, p.hemisphere as hemisphere,
                       p.timestamp as timestamp, p.metadata as metadata
                ORDER BY p.timestamp DESC
            """, skill_id=skill_id)
            return [dict(record["p"]) for record in result]
    
    def get_all(self, limit: int = 1000) -> list[dict[str, Any]]:
        """Get all procedural memories."""
        if self._driver is None:
            return []
        
        with self._driver.session() as session:
            result = session.run("""
                MATCH (p:ProceduralMemory)
                RETURN p.id as id, p.content as content,
                       p.skill_id as skill_id, p.hemisphere as hemisphere,
                       p.timestamp as timestamp, p.metadata as metadata
                ORDER BY p.timestamp DESC
                LIMIT $limit
            """, limit=limit)
            return [dict(record["p"]) for record in result]
    
    def search_skills(self, query: str) -> list[dict[str, Any]]:
        """Full-text search across procedural memory content."""
        if self._driver is None:
            return []
        
        with self._driver.session() as session:
            result = session.run("""
                CALL db.index.fulltext.queryNodes('procedural_content_search', $query)
                YIELD node, score
                RETURN node.id as id, node.content as content,
                       node.skill_id as skill_id, node.hemisphere as hemisphere,
                       node.timestamp as timestamp, node.metadata as metadata,
                       score
                ORDER BY score DESC
                LIMIT 20
            """, query=query)
            return [dict(record) for record in result]
    
    def get_related(
        self,
        entry_id: str,
        edge_type: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find related procedural memories via graph traversal.
        
        Args:
            entry_id: Source procedural memory ID.
            edge_type: Optional relationship type filter.
            limit: Maximum related nodes to return.
        
        Returns:
            List of related procedural memories with relationship info.
        """
        if self._driver is None:
            return []
        
        with self._driver.session() as session:
            if edge_type:
                result = session.run("""
                    MATCH (a:ProceduralMemory {id: $id})-[:REL {type: $edge_type}]->(b:ProceduralMemory)
                    RETURN b.id as id, b.content as content,
                           b.skill_id as skill_id, b.hemisphere as hemisphere,
                           b.timestamp as timestamp, b.metadata as metadata,
                           a_rel.strength as relationship_strength
                    ORDER BY a_rel.strength DESC
                    LIMIT $limit
                """, id=entry_id, edge_type=edge_type, limit=limit)
            else:
                result = session.run("""
                    MATCH (a:ProceduralMemory {id: $id})-[:REL]->(b:ProceduralMemory)
                    RETURN b.id as id, b.content as content,
                           b.skill_id as skill_id, b.hemisphere as hemisphere,
                           b.timestamp as timestamp, b.metadata as metadata,
                           a_rel.strength as relationship_strength,
                           a_rel.type as relationship_type
                    ORDER BY a_rel.strength DESC
                    LIMIT $limit
                """, id=entry_id, limit=limit)
            
            return [dict(record) for record in result]
    
    def get_skill_dependencies(self, skill_id: str) -> list[dict[str, Any]]:
        """Get all skills that a given skill depends on (graph traversal).
        
        Args:
            skill_id: The skill to find dependencies for.
        
        Returns:
            List of prerequisite skills.
        """
        if self._driver is None:
            return []
        
        with self._driver.session() as session:
            result = session.run("""
                MATCH (p:ProceduralMemory {skill_id: $skill_id})<-[:DEPENDS_ON]-(dep:ProceduralMemory)
                RETURN dep.id as id, dep.content as content,
                       dep.skill_id as skill_id, dep.hemisphere as hemisphere,
                       dep.timestamp as timestamp
                ORDER BY dep.timestamp DESC
            """, skill_id=skill_id)
            return [dict(record) for record in result]
    
    def get_skill_enhancements(self, skill_id: str) -> list[dict[str, Any]]:
        """Get all skills that enhance a given skill (upstream dependencies).
        
        Args:
            skill_id: The skill to find enhancements for.
        
        Returns:
            List of enhancing/related skills.
        """
        if self._driver is None:
            return []
        
        with self._driver.session() as session:
            result = session.run("""
                MATCH (p:ProceduralMemory {skill_id: $skill_id})<-[:ENHANCES]-(enh:ProceduralMemory)
                RETURN enh.id as id, enh.content as content,
                       enh.skill_id as skill_id, enh.hemisphere as hemisphere,
                       enh.timestamp as timestamp
                ORDER BY enh.timestamp DESC
            """, skill_id=skill_id)
            return [dict(record) for record in result]
    
    def backup(self) -> str:
        """Generate a DozerDB backup of the procedural memory database.
        
        This uses DozerDB's backup feature (not available in vanilla Neo4j Community).
        The backup is stored in the configured backup_dir.
        
        Returns:
            Backup file path or error message.
        """
        if self._driver is None:
            self.connect()
        
        import os
        import subprocess as sp
        from datetime import datetime as dt
        
        backup_dir = self.config.backup_dir
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"procedural_backup_{timestamp}.dump")
        
        try:
            result = sp.run(
                ["neo4j-admin", "database", "dump", "--to-path", backup_dir],
                capture_output=True, text=True, timeout=60,
            )
            
            if result.returncode == 0:
                return backup_path
            else:
                return f"Backup failed: {result.stderr}"
        except FileNotFoundError:
            return "neo4j-admin not found. Ensure Neo4j is installed and in PATH."
        except sp.TimeoutExpired:
            return "Backup timed out after 60 seconds."
    
    def close(self) -> None:
        """Close the Neo4j driver connection."""
        if self._driver:
            self._driver.close()
