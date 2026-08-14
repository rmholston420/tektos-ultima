"""
Tektos-Ultima-v1 — Initial Schema Migrations

v1 (barebones):
    - sessions (id, model, cwd, permission_mode, status, title, tag, root_session_id, timestamps, seq, ws_connections JSON)
    - events (id, session_id, event_type, data, created_at)

v2 (self-improvement):
    - sessions: add complexity, novelty_score, success_score, lessons JSON, skills_created JSON
    - experiences: new table for self-improvement records
    - meta_learning: new table for prompt patterns & model performance

v3 (dynamic learning):
    - sessions: add schema_version, evolution_log JSON
    - migrations: track which migrations were applied per session
    - skill_registry: new table for discovered/created skills
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def migrate_v1_to_v2(engine: object) -> None:
    """
    Add self-improvement fields to sessions, create experiences and meta_learning tables.

    This migration adds the fields the self-improvement engine needs to:
    - Track which task types succeed/fail per model
    - Store lessons learned per session
    - Persist experience records for future retrieval
    - Track meta-learning data (prompt patterns, model performance)
    """
    import sqlite3

    # Ensure we can connect to the event store DB
    from tektos.store.event_store import get_db_path

    db_path = get_db_path()

    if not db_path:
        log.warning("Event store DB path not set — skipping v1→v2 migration")
        return

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    try:
        # Add self-improvement fields to sessions (SQLite requires ALTER COLUMN for defaults)
        # SQLite doesn't support ALTER COLUMN ADD IF NOT EXISTS, so check first

        # Check if complexity column exists
        columns = conn.execute("PRAGMA table_info(sessions)").fetchall()
        column_names = {col[1] for col in columns}

        if "complexity" not in column_names:
            conn.execute("ALTER TABLE sessions ADD COLUMN complexity TEXT DEFAULT 'standard'")
        if "novelty_score" not in column_names:
            conn.execute("ALTER TABLE sessions ADD COLUMN novelty_score REAL DEFAULT 0.0")
        if "success_score" not in column_names:
            conn.execute("ALTER TABLE sessions ADD COLUMN success_score REAL DEFAULT 0.0")
        if "lessons" not in column_names:
            conn.execute("ALTER TABLE sessions ADD COLUMN lessons TEXT DEFAULT '[]'")
        if "skills_created" not in column_names:
            conn.execute("ALTER TABLE sessions ADD COLUMN skills_created TEXT DEFAULT '[]'")

        # Create experiences table for self-improvement records
        conn.execute("""
            CREATE TABLE IF NOT EXISTS experiences (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                task TEXT NOT NULL,
                model_used TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 0,
                tests_passed INTEGER DEFAULT 0,
                tests_total INTEGER DEFAULT 0,
                wall_time_seconds REAL DEFAULT 0.0,
                evaluation_score REAL DEFAULT 0.0,
                lessons TEXT DEFAULT '[]',
                what_worked TEXT DEFAULT '[]',
                what_failed TEXT DEFAULT '[]',
                what_to_avoid TEXT DEFAULT '[]',
                recommendations TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        # Create meta_learning table for prompt patterns & model performance
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meta_learning (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model TEXT NOT NULL,
                task_type TEXT NOT NULL,
                prompt_pattern TEXT,
                success INTEGER NOT NULL DEFAULT 0,
                quality_score REAL DEFAULT 0.0,
                failure_mode TEXT,
                avoidance_strategy TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                occurrence_count INTEGER DEFAULT 1,
                FOREIGN KEY (model) REFERENCES models(name)
            )
        """)

        # Create indexes for performance
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_experiences_session ON experiences(session_id)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_experiences_success ON experiences(success)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meta_learning_model ON meta_learning(model)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_meta_learning_task ON meta_learning(task_type)"
        )

        log.info("Migration v1→v2: self-improvement schema added")

    finally:
        conn.close()


def migrate_v2_to_v3(engine: object) -> None:
    """
    Add dynamic learning fields — schema_version, evolution_log, skill_registry.

    This migration enables the agent to:
    - Track which schema version each session was created under
    - Log schema changes as they happen (evolution trail)
    - Persist discovered/created skills in a dedicated registry
    - Support schema introspection for self-modification
    """
    import sqlite3

    from tektos.store.event_store import get_db_path

    db_path = get_db_path()

    if not db_path:
        log.warning("Event store DB path not set — skipping v2→v3 migration")
        return

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    try:
        # Check if schema_version column exists
        columns = conn.execute("PRAGMA table_info(sessions)").fetchall()
        column_names = {col[1] for col in columns}

        if "schema_version" not in column_names:
            conn.execute("ALTER TABLE sessions ADD COLUMN schema_version INTEGER DEFAULT 1")
        if "evolution_log" not in column_names:
            conn.execute("ALTER TABLE sessions ADD COLUMN evolution_log TEXT DEFAULT '[]'")

        # Create skill_registry table for discovered/created skills
        conn.execute("""
            CREATE TABLE IF NOT EXISTS skill_registry (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                category TEXT,
                description TEXT,
                trigger_conditions TEXT DEFAULT '[]',
                steps TEXT DEFAULT '[]',
                source TEXT DEFAULT 'agent_discovered',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version TEXT DEFAULT '0.1.0',
                is_active INTEGER DEFAULT 1,
                metadata TEXT DEFAULT '{}'
            )
        """)

        # Create indexes for skill_registry
        conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_registry_name ON skill_registry(name)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_skill_registry_category ON skill_registry(category)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_skill_registry_active ON skill_registry(is_active)"
        )

        # Update existing sessions to reflect new schema version
        conn.execute(
            "UPDATE sessions SET schema_version = 3 WHERE schema_version IS NULL OR schema_version < 3"
        )

        log.info("Migration v2→v3: dynamic learning schema added")

    finally:
        conn.close()


def apply_all_migrations(engine) -> list[int]:
    """
    Apply all initial migrations to the event store database.

    This is called once at app startup.

    Returns:
        list of applied version numbers
    """
    from tektos.migrations.engine import SchemaMigrationEngine

    if not isinstance(engine, SchemaMigrationEngine):
        raise TypeError(f"Expected SchemaMigrationEngine, got {type(engine)}")

    # Register migrations
    @engine.register_migration(2, "self_improvement_schema", reversible=True)
    def _migration_2(engine_obj):
        migrate_v1_to_v2(engine_obj)

    @engine.register_migration(3, "dynamic_learning_schema", reversible=True)
    def _migration_3(engine_obj):
        migrate_v2_to_v3(engine_obj)

    # Apply pending migrations
    applied = engine.apply_migrations()

    return applied
