"""Tests for database utility functions."""

import pytest
from tektos.utils.db_utils import (
    validate_table_name,
    escape_sql_identifier,
    sanitize_like_pattern,
    ALLOWED_TABLES,
    _TABLE_RE,
)


class TestTableRegex:
    """Tests for the _TABLE_RE regex pattern."""

    def test_valid_table_names(self):
        """Valid table names should match the regex."""
        assert _TABLE_RE.match("sessions")
        assert _TABLE_RE.match("trail")
        assert _TABLE_RE.match("state")
        assert _TABLE_RE.match("meta")
        assert _TABLE_RE.match("config")
        assert _TABLE_RE.match("_private")
        assert _TABLE_RE.match("a")
        assert _TABLE_RE.match("table_123")

    def test_invalid_table_names(self):
        """Invalid table names should not match the regex."""
        assert not _TABLE_RE.match("123table")  # starts with number
        assert not _TABLE_RE.match("table-name")  # hyphen
        assert not _TABLE_RE.match("table name")  # space
        assert not _TABLE_RE.match("table.name")  # dot
        assert not _TABLE_RE.match("")  # empty
        assert not _TABLE_RE.match("a" * 65)  # too long

    def test_max_length(self):
        """Table names should be limited to 64 characters."""
        assert _TABLE_RE.match("a" * 64)
        assert not _TABLE_RE.match("a" * 65)


class TestValidateTableName:
    """Tests for validate_table_name function."""

    def test_valid_table_in_allowed_list(self):
        """Valid table in allowed list should return True."""
        assert validate_table_name("sessions", "migrations") is True
        assert validate_table_name("trail", "migrations") is True
        assert validate_table_name("working", "memory") is True

    def test_invalid_table_raises_value_error(self):
        """Invalid table name should raise ValueError."""
        with pytest.raises(ValueError, match="not in allowed tables"):
            validate_table_name("nonexistent", "migrations")

    def test_module_scoping(self):
        """Different modules should have different allowed tables."""
        assert validate_table_name("sessions", "sessions") is True
        assert validate_table_name("sensory", "memory") is True
        with pytest.raises(ValueError):
            validate_table_name("sensory", "migrations")

    def test_default_module(self):
        """Default module should be 'migrations'."""
        assert validate_table_name("sessions") is True
        assert validate_table_name("trail") is True

    def test_sql_injection_prevention(self):
        """SQL injection attempts should be rejected."""
        with pytest.raises(ValueError):
            validate_table_name("sessions; DROP TABLE users", "migrations")
        with pytest.raises(ValueError):
            validate_table_name("sessions' OR '1'='1", "migrations")

    def test_case_sensitivity(self):
        """Table names should be case-sensitive."""
        with pytest.raises(ValueError):
            validate_table_name("Sessions", "migrations")  # capital S


class TestEscapeSqlIdentifier:
    """Tests for escape_sql_identifier function."""

    def test_escape_simple_identifier(self):
        """Simple identifiers should be wrapped in double quotes."""
        assert escape_sql_identifier("sessions") == '"sessions"'
        assert escape_sql_identifier("trail") == '"trail"'

    def test_escape_identifier_with_underscore(self):
        """Identifiers with underscores should be escaped."""
        assert escape_sql_identifier("state_meta") == '"state_meta"'

    def test_invalid_identifier_raises_error(self):
        """Invalid identifiers should raise ValueError."""
        with pytest.raises(ValueError):
            escape_sql_identifier("table-name")
        with pytest.raises(ValueError):
            escape_sql_identifier("123table")

    def test_escape_prevents_injection(self):
        """Escaped identifiers should prevent injection."""
        result = escape_sql_identifier("sessions")
        assert result == '"sessions"'
        assert result.count('"') == 2


class TestSanitizeLikePattern:
    """Tests for sanitize_like_pattern function."""

    def test_sanitize_percent(self):
        """Percent signs should be escaped."""
        result = sanitize_like_pattern("100%")
        assert "\\%" in result

    def test_sanitize_underscore(self):
        """Underscores should be escaped."""
        result = sanitize_like_pattern("user_name")
        assert "\\_" in result

    def test_sanitize_backslash(self):
        """Backslashes should be escaped."""
        result = sanitize_like_pattern("path\\to\\file")
        assert "\\\\" in result

    def test_sanitize_combined(self):
        """All special chars should be escaped."""
        result = sanitize_like_pattern("%_\\")
        assert "\\%" in result
        assert "\\_" in result
        assert "\\\\" in result

    def test_sanitize_normal_string(self):
        """Normal strings without special chars should be unchanged."""
        result = sanitize_like_pattern("hello world")
        assert result == "hello world"

    def test_sanitize_empty_string(self):
        """Empty string should return empty string."""
        result = sanitize_like_pattern("")
        assert result == ""

    def test_sanitize_prevents_injection(self):
        """Sanitized pattern should prevent LIKE injection."""
        # Malicious pattern trying to match everything
        malicious = "%'; DROP TABLE sessions; --"
        sanitized = sanitize_like_pattern(malicious)
        # The % should be escaped with backslash
        assert "\\%" in sanitized


class TestAllowedTables:
    """Tests for ALLOWED_TABLES constant."""

    def test_all_modules_defined(self):
        """All expected modules should be defined."""
        assert "sessions" in ALLOWED_TABLES
        assert "memory" in ALLOWED_TABLES
        assert "migrations" in ALLOWED_TABLES
        assert "postgres" in ALLOWED_TABLES
        assert "schema_evolution" in ALLOWED_TABLES

    def test_sessions_allowed_tables(self):
        """Sessions module should have correct allowed tables."""
        expected = {"sessions", "trail", "state", "meta", "config"}
        assert ALLOWED_TABLES["sessions"] == expected

    def test_memory_allowed_tables(self):
        """Memory module should have correct allowed tables."""
        expected = {"sensory", "working", "long_term", "procedural"}
        assert ALLOWED_TABLES["memory"] == expected

    def test_unknown_module_defaults_to_migrations(self):
        """Unknown module should default to migrations allowed tables."""
        # validate_table_name uses migrations as default
        assert validate_table_name("sessions", "unknown_module") is True
