"""Database utility functions for safe SQL operations.

Provides table name validation and SQL identifier escaping for SQLite/PostgreSQL.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Strict regex for SQL identifiers: must start with letter/underscore,
# contain only alphanumeric + underscore, max 64 chars
_TABLE_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]{0,63}$')

# Allowed tables per module (defense in depth)
ALLOWED_TABLES = {
    'sessions': {'sessions', 'trail', 'state', 'meta', 'config'},
    'memory': {'sensory', 'working', 'long_term', 'procedural'},
    'migrations': {'migrations', 'sessions', 'trail', 'state', 'meta', 'config'},
    'postgres': {'sensory', 'working', 'long_term', 'procedural'},
    'schema_evolution': {'sessions', 'trail', 'state', 'meta', 'config'},
}


def validate_table_name(table_name: str, module: str = 'migrations') -> bool:
    """Validate a table name against strict format and allowed tables whitelist.

    Args:
        table_name: The table name to validate.
        module: The module context (determines allowed tables).

    Returns:
        True if valid, False if invalid.

    Raises:
        ValueError: If table_name is invalid (with descriptive message).
    """
    if not table_name:
        raise ValueError("Table name cannot be empty")

    if not _TABLE_RE.match(table_name):
        raise ValueError(
            f"Invalid table name '{table_name}': "
            "must start with letter/underscore, contain only alphanumeric + underscore, "
            "max 64 characters"
        )

    allowed = ALLOWED_TABLES.get(module, ALLOWED_TABLES['migrations'])
    if table_name not in allowed:
        raise ValueError(
            f"Table '{table_name}' not in allowed tables for module '{module}': "
            f"{sorted(allowed)}"
        )

    return True


def escape_sql_identifier(identifier: str) -> str:
    """Escape a SQL identifier (table/column name) for safe use.

    For SQLite, identifiers are wrapped in double quotes if they need quoting.
    This does NOT prevent SQL injection by itself — use validate_table_name() first.

    Args:
        identifier: The SQL identifier to escape.

    Returns:
        Safely escaped identifier.

    Raises:
        ValueError: If identifier is invalid.
    """
    if not _TABLE_RE.match(identifier):
        raise ValueError(
            f"Invalid SQL identifier '{identifier}': "
            "must start with letter/underscore, contain only alphanumeric + underscore"
        )

    # SQLite identifiers: wrap in double quotes
    return f'"{identifier}"'


def sanitize_like_pattern(pattern: str) -> str:
    """Sanitize a LIKE pattern to prevent injection via wildcards.

    Args:
        pattern: The LIKE pattern to sanitize.

    Returns:
        Sanitized pattern with wildcards escaped.
    """
    # Escape special LIKE characters: %, _, \
    pattern = pattern.replace('\\', '\\\\')
    pattern = pattern.replace('%', '\\%')
    pattern = pattern.replace('_', '\\_')
    return pattern
