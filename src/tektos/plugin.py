"""Tektos Plugin System

Architecture:
- Built-in: existential to Tektos (event store, session manager, protocol, runtime, self-modification)
- Plugin: swappable, optional, extensible (providers, gateways, memory backends)
- Skill: reusable procedures stored in ~/.hermes/skills/ (not code)

Classification guide:
1. Built-in: Tektos cannot function without it
2. Plugin: Tektos works without it; user can swap backends
3. Skill: reusable procedures, not code modules

Current evaluation:
BUILT-IN:
- protocol/          — envelope format, 5W1H schema (existential contract)
- store/             — event store (append-only log, no replacement possible)
- runtime/           — session lifecycle, state machine (core execution)
- self_modification/ — self-test expander, GUI expander (self-improvement mandate)
- self_improvement/  — synthesis engine, experience replay (self-improvement mandate)
- agents/            — coder, planner, manager (Tektos's agent identity)
- ports/             — ProviderPort contract (the plugin interface itself)

PLUGIN:
- providers/         — search providers (SearXNG, Google, DDG, etc.)
- memory/            — Redis, Postgres, Neo4j, SQLite backends
- telegram_gateway.py — Telegram gateway (swappable for Discord/WhatsApp)

SKILL (already exists):
- ~/.hermes/skills/  — procedural memory, reusable patterns

"""

from abc import ABC, abstractmethod
from typing import Any, Optional

import yaml
from pydantic import BaseModel


class PluginConfig(BaseModel):
    """Base class for plugin configurations."""
    enabled: bool = True


class Plugin(ABC):
    """Base class for all Tektos plugins.

    All plugins must implement:
    - name: unique identifier
    - version: semantic version
    - config: plugin-specific configuration
    - initialize(): setup on plugin load
    - shutdown(): cleanup on plugin unload
    """

    def __init__(self) -> None:
        self._config: PluginConfig = PluginConfig()

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @property
    def config(self) -> PluginConfig:
        return self._config

    @config.setter
    def config(self, value: PluginConfig) -> None:
        self._config = value

    async def initialize(self) -> None:
        """Called when plugin is loaded. Override for setup."""
        pass

    async def shutdown(self) -> None:
        """Called when plugin is unloaded. Override for cleanup."""
        pass

    def __repr__(self) -> str:
        return f"<Plugin {self.name} v{self.version}>"


class PluginRegistry:
    """Central registry for loaded plugins.

    Manages plugin lifecycle:
    1. Load plugins from configured directories
    2. Initialize plugins in dependency order
    3. Track health and version compatibility
    4. Support hot-reload for development
    """

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._config: dict[str, Any] = {}

    def register(self, plugin: Plugin) -> None:
        """Register a plugin instance."""
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin {plugin.name!r} already registered")
        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> Optional[Plugin]:
        """Get a registered plugin by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> list[Plugin]:
        """List all registered plugins."""
        return list(self._plugins.values())

    async def initialize_all(self) -> None:
        """Initialize all registered plugins."""
        for plugin in self._plugins.values():
            await plugin.initialize()

    async def shutdown_all(self) -> None:
        """Shutdown all registered plugins."""
        for plugin in self._plugins.values():
            await plugin.shutdown()
            plugin.__dict__.clear()  # Force cleanup
