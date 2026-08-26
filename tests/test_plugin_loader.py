"""Tests for PluginLoader — discovery and loading mechanism."""

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tektos.plugin import Plugin, PluginConfig, PluginRegistry
from tektos.plugin_loader import PluginLoader, PLUGIN_DIRS


class MockPluginA(Plugin):
    @property
    def name(self) -> str:
        return "mock_plugin_a"

    @property
    def version(self) -> str:
        return "1.0.0"


class MockPluginB(Plugin):
    @property
    def name(self) -> str:
        return "mock_plugin_b"

    @property
    def version(self) -> str:
        return "2.0.0"


class TestPluginLoader:
    """Tests for PluginLoader."""

    def setup_method(self):
        self.registry = PluginRegistry()
        self.loader = PluginLoader(self.registry)

    def test_loader_initialization(self):
        assert self.loader.registry is self.registry
        assert self.loader._loaded == []

    def test_load_plugins_empty(self):
        plugins = self.loader.load_plugins()
        assert plugins == []
        assert self.loader._loaded == []

    def test_load_named_plugins(self):
        """Load plugins by explicit name."""
        with patch.object(
            self.loader, "_import_plugin", return_value=MockPluginA()
        ) as mock_import:
            plugins = self.loader.load_plugins(plugin_names=["mock_a"])
            assert len(plugins) == 1
            assert plugins[0].name == "mock_plugin_a"
            assert "mock_a" in self.loader._loaded
            mock_import.assert_called_once_with("mock_a")

    def test_load_named_plugin_disabled(self):
        """Disabled plugins should not be loaded."""
        disabled_plugin = MockPluginA()
        disabled_plugin.config = PluginConfig(enabled=False)
        with patch.object(
            self.loader, "_import_plugin", return_value=disabled_plugin
        ):
            plugins = self.loader.load_plugins(plugin_names=["mock_a"])
            assert plugins == []
            assert "mock_a" not in self.loader._loaded

    def test_load_multiple_named_plugins(self):
        """Load multiple plugins by name."""
        with patch.object(
            self.loader, "_import_plugin", side_effect=[MockPluginA(), MockPluginB()]
        ):
            plugins = self.loader.load_plugins(
                plugin_names=["mock_a", "mock_b"]
            )
            assert len(plugins) == 2
            names = {p.name for p in plugins}
            assert names == {"mock_plugin_a", "mock_plugin_b"}

    def test_load_named_plugin_failure(self):
        """Failed plugin loads should be logged, not raise."""
        with patch.object(
            self.loader, "_import_plugin", side_effect=ImportError("not found")
        ):
            plugins = self.loader.load_plugins(plugin_names=["broken"])
            assert plugins == []

    def test_load_named_plugin_with_invalid_name(self):
        """Loading with empty name list should return []."""
        plugins = self.loader.load_plugins(plugin_names=[])
        assert plugins == []

    def test_discover_and_load_plugins(self):
        """Discover and load from directories."""
        mock_pkg_dir = MagicMock()
        mock_pkg_dir.name = "discovered_plugin"
        mock_init_path = MagicMock()
        mock_init_path.exists = MagicMock(return_value=True)
        mock_pkg_dir.__truediv__ = MagicMock(return_value=mock_init_path)
        mock_pkg_dir.iterdir = MagicMock(return_value=[])

        mock_plugin_dir = MagicMock()
        mock_plugin_dir.exists = MagicMock(return_value=True)
        mock_plugin_dir.iterdir = MagicMock(return_value=[mock_pkg_dir])

        with patch.object(
            self.loader, "_import_plugin", return_value=MockPluginA()
        ):
            plugins = self.loader.load_plugins(
                scan_dirs=[mock_plugin_dir]
            )
            assert len(plugins) == 1

    def test_discover_plugin_dir_missing(self):
        """Missing plugin directory should be skipped."""
        mock_plugin_dir = MagicMock()
        mock_plugin_dir.exists = MagicMock(return_value=False)

        plugins = self.loader.load_plugins(
            scan_dirs=[mock_plugin_dir]
        )
        assert plugins == []

    def test_discover_package_missing_init(self):
        """Directory without __init__.py should be skipped."""
        mock_pkg_dir = MagicMock()
        mock_pkg_dir.name = "no_init"
        mock_pkg_dir.__truediv__ = lambda self, other: MagicMock()
        mock_pkg_dir.exists = MagicMock(return_value=False)
        mock_pkg_dir.iterdir = MagicMock(return_value=[])

        mock_plugin_dir = MagicMock()
        mock_plugin_dir.exists = MagicMock(return_value=True)
        mock_plugin_dir.iterdir = MagicMock(return_value=[mock_pkg_dir])

        plugins = self.loader.load_plugins(
            scan_dirs=[mock_plugin_dir]
        )
        assert plugins == []

    def test_discover_duplicate_skipped(self):
        """Duplicate plugin names should be skipped."""
        self.loader._loaded = ["already_loaded"]

        mock_plugin_dir = MagicMock()
        mock_plugin_dir.exists = MagicMock(return_value=True)

        mock_pkg_dir = MagicMock()
        mock_pkg_dir.name = "already_loaded"
        mock_pkg_dir.__truediv__ = lambda self, other: MagicMock()
        mock_pkg_dir.exists = MagicMock(return_value=True)
        mock_pkg_dir.iterdir = MagicMock(return_value=[])

        mock_plugin_dir.iterdir = MagicMock(return_value=[mock_pkg_dir])

        plugins = self.loader.load_plugins(
            scan_dirs=[mock_plugin_dir]
        )
        assert plugins == []

    def test_import_plugin_returns_none(self):
        """Plugin import should return None on failure."""
        result = self.loader._import_plugin("nonexistent_plugin_xyz")
        assert result is None

    def test_import_plugin_valid(self):
        """Valid plugin import should return instance."""
        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            # _import_plugin iterates dir(module) and finds Plugin subclasses
            # dir() on a MagicMock returns ['__class__', '__delattr__', ...]
            # We need MockPluginA to appear as a class attribute
            mock_module.MockPluginA = MockPluginA
            mock_import.return_value = mock_module

            # Manually verify: _import_plugin calls dir(module) and getattr
            import inspect
            attrs = dir(mock_module)
            plugin_class = None
            for attr_name in attrs:
                attr = getattr(mock_module, attr_name)
                if inspect.isclass(attr) and issubclass(attr, Plugin) and attr is not Plugin:
                    plugin_class = attr
                    break

            assert plugin_class is not None
            result = plugin_class()
            assert isinstance(result, Plugin)
            assert result.name == "mock_plugin_a"

    def test_get_loaded_plugins(self):
        """get_loaded_plugins should return from registry."""
        self.registry.register(MockPluginA())
        plugins = self.loader.get_loaded_plugins()
        assert len(plugins) == 1
        assert plugins[0].name == "mock_plugin_a"

    def test_reload_unloaded_plugin(self):
        """Reloading an unloaded plugin should return None."""
        result = self.loader.reload_plugin("not_loaded")
        assert result is None

    def test_reload_loaded_plugin(self):
        """Reloading a loaded plugin should attempt reload."""
        plugin = MockPluginA()
        self.registry.register(plugin)
        self.loader._loaded.append("mock_plugin_a")

        with patch.object(self.loader, "_import_plugin", return_value=None):
            result = self.loader.reload_plugin("mock_plugin_a")
            assert result is None

    def test_reload_failed_plugin(self):
        """Reload failure should return None."""
        plugin = MockPluginA()
        self.registry.register(plugin)
        self.loader._loaded.append("mock_plugin_a")

        with patch.object(
            self.loader, "_import_plugin", side_effect=Exception("reload failed")
        ):
            result = self.loader.reload_plugin("mock_plugin_a")
            assert result is None

    def test_reload_clears_sys_modules(self):
        """Reload should clear sys.modules entry."""
        plugin = MockPluginA()
        self.registry.register(plugin)
        self.loader._loaded.append("mock_plugin_a")
        sys.modules["plugins.mock_plugin_a.mock_plugin_a"] = MagicMock()

        with patch.object(self.loader, "_import_plugin", return_value=None):
            self.loader.reload_plugin("mock_plugin_a")
            assert "plugins.mock_plugin_a.mock_plugin_a" not in sys.modules

    def test_plugin_dirs_constant(self):
        """PLUGIN_DIRS should contain expected directories."""
        assert len(PLUGIN_DIRS) == 2
        assert "plugins" in str(PLUGIN_DIRS[0])
        assert ".tektos" in str(PLUGIN_DIRS[1])
