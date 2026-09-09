"""Tektos-Ultima — ProviderPort contracts.

This module defines the plugin interface referenced in
``docs/tektos-architectural-classification.md`` and in the
``src/tektos/plugin.py`` classification header. Every swappable
"provider" plugin (search, sandbox, vision, LLM, memory backend, gateway)
implements at minimum :class:`ProviderPort` and MAY also implement one
of the capability-specific Protocols (:class:`SearchProviderPort`,
:class:`SandboxProviderPort`, :class:`VisionProviderPort`,
:class:`LLMProviderPort`, :class:`GatewayProviderPort`) so the runtime
can select an interchangeable implementation at boot.

Design notes
------------

* The base :class:`ProviderPort` is deliberately lightweight (name, kind,
  version, start/stop/health). Kind-specific verbs live on the
  capability Protocols so existing providers can adopt the contract
  incrementally without renaming ``search()``, ``execute()``, or
  ``analyze()``.

* Protocols are ``runtime_checkable`` so ``isinstance(obj, SearchProviderPort)``
  works. That lets consumers such as the future ``PluginRegistry.select_by_kind``
  look up available implementations without maintaining a separate table.

* This module is import-free apart from ``typing`` and ``abc`` so it can be
  imported by any plugin without pulling in httpx / pydantic / heavy deps.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Literal, Protocol, runtime_checkable

# Kinds a provider can advertise. Keep this string-typed rather than an
# Enum so third-party plugins can extend without modifying core code.
ProviderKind = Literal[
    "search",
    "sandbox",
    "vision",
    "llm",
    "memory",
    "gateway",
    "other",
]


@runtime_checkable
class ProviderPort(Protocol):
    """Base contract every Tektos provider plugin must satisfy.

    Concrete providers do not have to inherit from this class — they only
    have to expose the attributes and methods below. That keeps the door
    open for both class-based and simple duck-typed provider adapters.
    """

    #: Unique, human-readable identifier (e.g. ``"searxng"``, ``"local-sandbox"``).
    name: str
    #: Capability category — used by the runtime to pick a provider.
    kind: ProviderKind
    #: Semantic version of the provider adapter (not the underlying service).
    version: str

    async def start(self) -> None:
        """Open connections, warm caches, register listeners.

        Called once during ``lifespan()``. Idempotent implementations are
        strongly encouraged — the runtime may call ``start()`` again after
        a health-driven restart.
        """
        ...

    async def stop(self) -> None:
        """Release resources acquired in ``start()``.

        Always called during shutdown, even if ``start()`` raised. Must
        not raise on already-stopped providers.
        """
        ...

    async def health(self) -> bool:
        """Return ``True`` when the provider can serve requests right now.

        Called by ``/api/plugins/list`` and by the self-repair recovery
        layer. Cheap and non-blocking is the goal — do not run a full
        request just to answer this.
        """
        ...


# ── Capability-specific Protocols ────────────────────────────────────────────
#
# Every capability Protocol extends ``ProviderPort`` so providers only need
# to declare one interface. They exist so callers can type-narrow (e.g.
# ``def query(port: SearchProviderPort) -> ...``) without importing the
# concrete adapter.


@runtime_checkable
class SearchProviderPort(ProviderPort, Protocol):
    """Providers that answer text/web search queries."""

    kind: Literal["search"]  # type: ignore[assignment]

    @abstractmethod
    async def search(
        self, query: str, *, limit: int = 10, **options: Any
    ) -> list[dict[str, Any]]:
        """Return a list of hit dicts.

        Every hit MUST contain at least ``url``, ``title``, ``snippet``.
        Extra fields (score, source, published_at) are welcome.
        """
        ...


@runtime_checkable
class SandboxProviderPort(ProviderPort, Protocol):
    """Providers that execute tool calls in a sandboxed environment."""

    kind: Literal["sandbox"]  # type: ignore[assignment]

    @abstractmethod
    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute ``tool_name`` synchronously and return its stdout.

        Errors must raise; do not return error strings.
        """
        ...


@runtime_checkable
class VisionProviderPort(ProviderPort, Protocol):
    """Providers that answer image/vision questions."""

    kind: Literal["vision"]  # type: ignore[assignment]

    @abstractmethod
    async def analyze(
        self,
        image: bytes | str,
        prompt: str,
        **options: Any,
    ) -> dict[str, Any]:
        """Analyze an image (bytes or path) with a natural-language prompt."""
        ...


@runtime_checkable
class LLMProviderPort(ProviderPort, Protocol):
    """Providers that back the primary chat/completion endpoint."""

    kind: Literal["llm"]  # type: ignore[assignment]

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        **options: Any,
    ) -> dict[str, Any]:
        """Non-streaming chat completion. Must return a dict with ``choices``."""
        ...


@runtime_checkable
class GatewayProviderPort(ProviderPort, Protocol):
    """Providers that carry messages to/from an external chat surface
    (Telegram, Discord, WhatsApp, email, SMS)."""

    kind: Literal["gateway"]  # type: ignore[assignment]

    @abstractmethod
    async def send_message(self, chat_id: str, text: str, **options: Any) -> None:
        """Deliver ``text`` to ``chat_id`` on the underlying transport."""
        ...


__all__ = [
    "GatewayProviderPort",
    "LLMProviderPort",
    "ProviderKind",
    "ProviderPort",
    "SandboxProviderPort",
    "SearchProviderPort",
    "VisionProviderPort",
]
