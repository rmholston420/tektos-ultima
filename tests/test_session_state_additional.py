"""Additional tests for session_state.py — covering uncovered lines."""

from datetime import datetime, timezone

import pytest

from tektos.runtime.session_state import SessionState


class TestSessionStateAdditionalParsing:
    """Tests for uncovered parsing paths."""

    def test_parse_current_file(self):
        """Parse current_file from markdown — line 218."""
        md = f"""# LAST_KNOWN_STATE.md
**Session:** s1
**Project:** P
**Timestamp:** 2026-01-01T00:00:00+00:00

## Current State

- **Current File:** `src/tektos/main.py`
- **Current Command:** `pytest tests/`

**Progress:** in progress
"""
        state = SessionState.from_markdown(md, "s1", "P")
        assert state.current_file == "src/tektos/main.py"

    def test_next_steps_split_on_section_header(self):
        """Split on \\n## when Next Steps is followed by another section — line 225."""
        md = f"""# LAST_KNOWN_STATE.md
**Session:** s1
**Project:** P
**Timestamp:** 2026-01-01T00:00:00+00:00

## Next Steps

1. Write test
2. Run coverage
3. Fix bugs

## Key Decisions

1. Use aiogram 3.x
"""
        state = SessionState.from_markdown(md, "s1", "P")
        assert state.next_steps == ["Write test", "Run coverage", "Fix bugs"]

    def test_key_decisions_split_on_section_header(self):
        """Split on \\n## when Key Decisions is followed by another section — line 238."""
        md = f"""# LAST_KNOWN_STATE.md
**Session:** s1
**Project:** P
**Timestamp:** 2026-01-01T00:00:00+00:00

## Key Decisions

1. Use aiogram 3.x
2. SQLite for events
3. Telegram prioritized

## Next Steps

1. Write integration test
"""
        state = SessionState.from_markdown(md, "s1", "P")
        assert state.key_decisions == ["Use aiogram 3.x", "SQLite for events", "Telegram prioritized"]

    def test_blockers_split_on_section_header(self):
        """Split on \\n## when Blockers is followed by another section — line 249."""
        md = f"""# LAST_KNOWN_STATE.md
**Session:** s1
**Project:** P
**Timestamp:** 2026-01-01T00:00:00+00:00

## Blockers

- 🚫 LLM endpoint down
- 🚫 Missing config

## Next Steps

1. Restart LLM
"""
        state = SessionState.from_markdown(md, "s1", "P")
        assert "LLM endpoint down" in state.blockers
        assert "Missing config" in state.blockers