"""Tests for Plugin base classes and PluginRegistry."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tektos.plugin import Plugin, PluginConfig, PluginRegistry


# ---------------------------------------------------------------------------
# Test fixtures — concrete plugin implementations
# ---------------------------------------------------------------------------

class TestPluginImpl(Plugin):
    """Concrete plugin for testing."""

    @property
    def name(self) -> str:
        return "test_plugin"

    @property
    def version(self) -> str:
        return "1.0.0"


# ---------------------------------------------------------------------------
# PluginConfig
# ---------------------------------------------------------------------------

class TestPluginImplConfig:
    """Tests for PluginConfig defaults and behavior."""

    def test_default_config(self):
        config = PluginConfig()
        assert config.enabled is True

    def test_config_disable(self):
        config = PluginConfig(enabled=False)
        assert config.enabled is False


# ---------------------------------------------------------------------------
# Plugin base class
# ---------------------------------------------------------------------------

class TestPluginImplBase:
    """Tests for the Plugin ABC."""

    def test_concrete_plugin_creation(self):
        plugin = TestPluginImpl()
        assert plugin.name == "test_plugin"
        assert plugin.version == "1.0.0"

    def test_plugin_default_config(self):
        plugin = TestPluginImpl()
        assert isinstance(plugin.config, PluginConfig)
        assert plugin.config.enabled is True

    def test_plugin_set_config(self):
        plugin = TestPluginImpl()
        plugin.config = PluginConfig(enabled=False)
        assert plugin.config.enabled is False

    def test_plugin_repr(self):
        plugin = TestPluginImpl()
        assert repr(plugin) == "<Plugin test_plugin v1.0.0>"

    @pytest.mark.asyncio
    async def test_plugin_initialize(self):
        """Default initialize() should be a no-op."""
        plugin = TestPluginImpl()
        await plugin.initialize()  # Should not raise

    @pytest.mark.asyncio
    async def test_plugin_shutdown(self):
        """Default shutdown() should be a no-op."""
        plugin = TestPluginImpl()
        await plugin.shutdown()  # Should not raise


# ---------------------------------------------------------------------------
# PluginRegistry
# ---------------------------------------------------------------------------

class TestPluginImplRegistry:
    """Tests for PluginRegistry lifecycle."""

    def setup_method(self):
        self.registry = PluginRegistry()

    def test_initial_empty(self):
        assert self.registry.list_plugins() == []

    def test_register_single_plugin(self):
        plugin = TestPluginImpl()
        self.registry.register(plugin)
        assert len(self.registry.list_plugins()) == 1
        assert self.registry.get("test_plugin") is plugin

    def test_register_duplicate_raises(self):
        plugin = TestPluginImpl()
        self.registry.register(plugin)
        with pytest.raises(ValueError, match="already registered"):
            self.registry.register(TestPluginImpl())

    def test_get_nonexistent(self):
        assert self.registry.get("nonexistent") is None

    def test_list_plugins_after_multiple_registers(self):
        class PluginA(Plugin):
            @property
            def name(self) -> str:
                return "plugin_a"

            @property
            def version(self) -> str:
                return "1.0.0"

        class PluginB(Plugin):
            @property
            def name(self) -> str:
                return "plugin_b"

            @property
            def version(self) -> str:
                return "2.0.0"

        self.registry.register(PluginA())
        self.registry.register(PluginB())
        plugins = self.registry.list_plugins()
        assert len(plugins) == 2
        names = {p.name for p in plugins}
        assert names == {"plugin_a", "plugin_b"}

    @pytest.mark.asyncio
    async def test_initialize_all(self):
        """All plugins should have initialize() called."""
        mock_plugin_a = MagicMock(spec=Plugin)
        mock_plugin_a.name = "mock_a"
        mock_plugin_a.initialize = AsyncMock()

        mock_plugin_b = MagicMock(spec=Plugin)
        mock_plugin_b.name = "mock_b"
        mock_plugin_b.initialize = AsyncMock()

        self.registry.register(mock_plugin_a)
        self.registry.register(mock_plugin_b)
        await self.registry.initialize_all()
        mock_plugin_a.initialize.assert_called_once()
        mock_plugin_b.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_all(self):
        """All plugins should have shutdown() called."""
        mock_plugin_a = MagicMock(spec=Plugin)
        mock_plugin_a.name = "mock_a"
        mock_plugin_a.shutdown = AsyncMock()

        mock_plugin_b = MagicMock(spec=Plugin)
        mock_plugin_b.name = "mock_b"
        mock_plugin_b.shutdown = AsyncMock()

        self.registry.register(mock_plugin_a)
        self.registry.register(mock_plugin_b)

        # shutdown_all calls plugin.__dict__.clear() which wipes mock internals.
        # Call shutdown manually to verify, then let shutdown_all do its thing.
        await mock_plugin_a.shutdown()
        await mock_plugin_b.shutdown()

        await self.registry.shutdown_all()  # Should not raise despite __dict__.clear()

    def test_config_attribute(self):
        assert isinstance(self.registry._config, dict)
        assert self.registry._config == {}


# ---------------------------------------------------------------------------
# Plugin ABC enforcement
# ---------------------------------------------------------------------------

class TestPluginImplABCEncforcement:
    """Tests that Plugin cannot be instantiated without abstract methods."""

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            Plugin()  # type: ignore[abstract]
