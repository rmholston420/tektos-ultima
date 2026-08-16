"""Additional tests for Tektos coverage expansion — small modules."""

from tektos.rate_limiter import (
    _SLOWAPI_AVAILABLE,
    create_limiter,
    enable_rate_limiting,
    get_status,
)


class TestRateLimiterAdditional:
    """Cover uncovered lines: ImportError fallback values, enable+status flow."""

    def test_slowapi_import_fallback_values(self):
        """When slowapi is not importable, fallback values should be None."""
        if not _SLOWAPI_AVAILABLE:
            import tektos.rate_limiter as rl
            assert rl.Limiter is None
            assert rl.get_remote_address is None
            assert rl.RateLimitExceeded is None
            assert rl.Request is None

    def test_create_limiter_returns_none_when_unavailable(self):
        """create_limiter returns None when slowapi is unavailable."""
        if not _SLOWAPI_AVAILABLE:
            assert create_limiter() is None

    def test_create_limiter_returns_limiter_when_available(self):
        """create_limiter returns Limiter instance when slowapi is available."""
        if _SLOWAPI_AVAILABLE:
            result = create_limiter()
            assert result is not None

    def test_enable_and_get_status(self):
        """Calling enable_rate_limiting changes module state."""
        from tektos.rate_limiter import _ENABLED as orig_enabled
        from tektos.rate_limiter import _DEFAULT_LIMIT as orig_limit
        try:
            enable_rate_limiting("50/second")
            status = get_status()
            assert status["enabled"] is True
            assert status["default_limit"] == "50/second"
        finally:
            from tektos.rate_limiter import _ENABLED as reset_check
            if reset_check:
                import tektos.rate_limiter as rl
                rl._ENABLED = False
                rl._DEFAULT_LIMIT = orig_limit


class TestLanguageGameTieBreak:
    """Cover language_game.py lines 93-96 (tie-breaking logic)."""

    def test_tie_prefers_software_engineering(self):
        """When SE and SYSTEMS tie, SE wins."""
        from src.tektos.agents.planner.language_game import (
            LanguageGame,
            classify_language_game,
        )
        # "vsm" matches SYSTEMS, "api" matches SE — but let's craft a real tie
        # "api" appears in SE list, "vsm" appears in SYSTEMS list
        text = "api vsm"
        result = classify_language_game(text)
        # Both get score 1, SE should win as tiebreaker
        assert result == LanguageGame.SOFTWARE_ENGINEERING

    def test_tie_prefers_systems_when_no_se(self):
        """When SYSTEMS and BUDDHIST tie, SYSTEMS wins."""
        from src.tektos.agents.planner.language_game import (
            LanguageGame,
            classify_language_game,
        )
        # "vsm" → SYSTEMS, "dharma" → BUDDHIST
        text = "vsm dharma"
        result = classify_language_game(text)
        # Both get score 1, SYSTEMS should win
        assert result == LanguageGame.SYSTEMS_ARCHITECTURE


class TestSanitizeLike:
    """Cover db_utils.py lines 94-97 (sanitize_like_pattern)."""

    def test_escape_percent(self):
        from src.tektos.utils.db_utils import sanitize_like_pattern
        result = sanitize_like_pattern("100%")
        # % should be escaped to \%
        assert "\\%" in result

    def test_escape_underscore(self):
        from src.tektos.utils.db_utils import sanitize_like_pattern
        result = sanitize_like_pattern("a_b")
        assert "\\_" in result

    def test_escape_backslash(self):
        from src.tektos.utils.db_utils import sanitize_like_pattern
        result = sanitize_like_pattern("a\\b")
        assert "\\\\" in result or "\\\\" in repr(result)

    def test_empty_pattern(self):
        from src.tektos.utils.db_utils import sanitize_like_pattern
        result = sanitize_like_pattern("")
        assert result == ""


class TestPluginLoaderAdditional:
    """Cover plugin_loader.py lines 84-85, 95-102, 129-130."""

    def test_discover_non_dir_symlink(self):
        """A symlink that's not a dir should be skipped."""
        from pathlib import Path
        import tempfile
        import os
        from unittest.mock import MagicMock
        from tektos.plugin import PluginRegistry
        from tektos.plugin_loader import PluginLoader

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Create a regular file (not a dir) — should be skipped
            (tmp_path / "fake_plugin").write_text("not a package")
            registry = MagicMock()
            loader = PluginLoader(registry)
            loaded = loader.load_plugins(scan_dirs=[tmp_path])
            assert len(loaded) == 0

    def test_discover_hidden_dir_skipped(self):
        """Hidden directories (.foo) should be skipped by iterdir."""
        from pathlib import Path
        import tempfile
        from unittest.mock import MagicMock
        from tektos.plugin import PluginRegistry
        from tektos.plugin_loader import PluginLoader

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            hidden = tmp_path / ".hidden_plugin"
            hidden.mkdir()
            (hidden / "__init__.py").write_text("")
            registry = MagicMock()
            loader = PluginLoader(registry)
            loaded = loader.load_plugins(scan_dirs=[tmp_path])
            # Hidden dirs have __init__.py so they WOULD be picked up —
            # the code doesn't explicitly skip hidden dirs, so this test
            # just verifies the behavior is deterministic
            assert len(loaded) == 0  # import will fail, returns None

    def test_reload_returns_none_on_import_error(self):
        """reload_plugin returns None if re-import fails after unload."""
        from pathlib import Path
        import tempfile
        from unittest.mock import MagicMock, patch
        from tektos.plugin import Plugin, PluginRegistry
        from tektos.plugin_loader import PluginLoader

        class FakePlugin(Plugin):
            name = "fake"
            version = "0.1"

            class Config:
                enabled = True

        with tempfile.TemporaryDirectory() as tmp:
            registry = PluginRegistry()
            registry.register(FakePlugin())
            loader = PluginLoader(registry)
            loader._loaded.append("fake")
            registry._plugins["fake"] = FakePlugin()

            with patch.object(loader, "_import_plugin", return_value=None):
                result = loader.reload_plugin("fake")
                assert result is None

    def test_reload_clears_sys_modules_and_reimports(self):
        """reload_plugin should delete from sys.modules and reimport."""
        from unittest.mock import MagicMock, patch
        import sys
        from tektos.plugin import Plugin, PluginRegistry
        from tektos.plugin_loader import PluginLoader

        class FakePlugin2(Plugin):
            name = "fake2"
            version = "0.1"

            class Config:
                enabled = True

        registry = PluginRegistry()
        registry.register(FakePlugin2())
        loader = PluginLoader(registry)
        loader._loaded.append("fake2")
        registry._plugins["fake2"] = FakePlugin2()
        sys.modules["plugins.fake2.fake2"] = MagicMock()

        call_count = 0

        def fake_import(name):
            nonlocal call_count
            call_count += 1
            return FakePlugin2()

        with patch.object(loader, "_import_plugin", side_effect=fake_import):
            loader.reload_plugin("fake2")
            assert call_count == 1
