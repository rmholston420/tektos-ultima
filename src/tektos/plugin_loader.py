"""Plugin loader — discovers and loads Tektos plugins."""

from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from tektos.plugin import Plugin, PluginRegistry

logger = logging.getLogger(__name__)

# Plugin directories to scan (in order of priority)
PLUGIN_DIRS = [
    Path(__file__).parent.parent.parent / "plugins",  # /plugins/
    Path.home() / ".tektos" / "plugins",              # ~/.tektos/plugins/
]


class PluginLoader:
    """Discovers and loads plugins from configured directories."""

    def __init__(self, registry: PluginRegistry) -> None:
        self.registry = registry
        self._loaded: list[str] = []

    def load_plugins(
        self,
        plugin_names: Optional[list[str]] = None,
        scan_dirs: Optional[list[Path]] = None,
    ) -> list[Plugin]:
        """Load plugins by name or discover from directories.

        Args:
            plugin_names: Explicit plugin names to load (e.g. ["searxng", "discord"]).
            scan_dirs: Directories to scan for plugins. Defaults to PLUGIN_DIRS.

        Returns:
            List of loaded plugin instances.
        """
        scan_dirs = scan_dirs or PLUGIN_DIRS

        if plugin_names:
            return self._load_named_plugins(plugin_names)
        return self._discover_and_load_plugins(scan_dirs)

    def _load_named_plugins(self, names: list[str]) -> list[Plugin]:
        """Load plugins by explicit name."""
        loaded: list[Plugin] = []
        for name in names:
            try:
                plugin = self._import_plugin(name)
                if plugin and plugin.config.enabled:
                    self.registry.register(plugin)
                    loaded.append(plugin)
                    self._loaded.append(name)
                    logger.info("Loaded plugin: %s", name)
            except Exception as e:
                logger.error("Failed to load plugin %s: %s", name, e)
        return loaded

    def _discover_and_load_plugins(self, dirs: list[Path]) -> list[Plugin]:
        """Scan directories for plugins and load enabled ones."""
        loaded: list[Plugin] = []
        for plugin_dir in dirs:
            if not plugin_dir.exists():
                continue
            for pkg_dir in plugin_dir.iterdir():
                if not (pkg_dir / "__init__.py").exists():
                    continue
                plugin_name = pkg_dir.name
                # Skip if already loaded
                if plugin_name in self._loaded:
                    continue
                try:
                    plugin = self._import_plugin(plugin_name)
                    if plugin and plugin.config.enabled:
                        self.registry.register(plugin)
                        loaded.append(plugin)
                        self._loaded.append(plugin_name)
                        logger.info("Discovered and loaded plugin: %s", plugin_name)
                except Exception as e:
                    logger.error(
                        "Failed to discover plugin %s: %s", plugin_name, e
                    )
        return loaded

    def _import_plugin(self, name: str) -> Optional[Plugin]:
        """Import a plugin by module name."""
        try:
            module = importlib.import_module(f"plugins.{name}.{name}")
            # Look for a class that inherits from Plugin
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Plugin)
                    and attr is not Plugin
                ):
                    return attr()
        except ImportError as e:
            logger.warning(
                "Plugin %s not found: %s", name, e
            )
        return None

    def get_loaded_plugins(self) -> list[Plugin]:
        """Return list of currently loaded plugins."""
        return list(self.registry.list_plugins())

    def reload_plugin(self, name: str) -> Optional[Plugin]:
        """Hot-reload a plugin (development use only)."""
        if name not in self._loaded:
            logger.warning("Plugin %s not loaded, cannot reload", name)
            return None
        # Unload
        if name in self.registry._plugins:
            plugin = self.registry._plugins[name]
            self.registry._plugins.pop(name)
        # Force re-import
        if f"plugins.{name}.{name}" in sys.modules:
            del sys.modules[f"plugins.{name}.{name}"]
        # Reload
        try:
            plugin = self._import_plugin(name)
            if plugin and plugin.config.enabled:
                self.registry.register(plugin)
                logger.info("Reloaded plugin: %s", name)
            return plugin
        except Exception as e:
            logger.error("Failed to reload plugin %s: %s", name, e)
            return None
